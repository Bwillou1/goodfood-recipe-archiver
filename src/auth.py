"""Connexion RÉELLE à Goodfood — Authentification Robuste, Sécurisée & Sans Faux Succès.

Garanties P0 :
- Ne persiste JAMAIS une session ratée (validation réelle par cookie fbtoken/GF3 ou page /recipe-cards).
- Détection ciblée des erreurs explicites dans le formulaire de connexion.
- Retry intelligent sur timeout réseau (sans boucler sur mauvais mot de passe).
- Dump de diagnostic (screenshot + HTML tronqué dans data/cache/login_fail.*) uniquement en cas d'échec avéré.
- Typage strict et propre.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .guardrails import apply_guardrails, apply_guardrails_async
from .utils import (
    CACHE_DIR, CHROMIUM_PERF_ARGS, ensure_dirs, get_credentials, load_config, storage_state_path,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser as AsyncBrowser, BrowserContext as AsyncContext, Page as AsyncPage
    from playwright.sync_api import BrowserContext as SyncContext, Page as SyncPage


def is_storage_state_fresh() -> bool:
    """Vérifie localement si storage_state.json contient un token de session non expiré."""
    state_path = storage_state_path()
    if not state_path.exists():
        return False
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        cookies = {c["name"]: c for c in data.get("cookies", [])}
        if "fbtoken" not in cookies and "GF3" not in cookies:
            return False
        now = time.time()
        for name in ("fbtoken", "GF_LOCATION"):
            if name in cookies:
                exp = cookies[name].get("expires", -1)
                if exp > 0 and exp < now:
                    return False
        return True
    except Exception:
        return False


async def is_logged_in_async(context: AsyncContext, probe_url: str) -> bool:
    """Vérifie la validité de la session par la présence d'éléments sur /recipe-cards."""
    page = await context.new_page()
    await apply_guardrails_async(page)
    try:
        await page.goto(probe_url, wait_until="domcontentloaded", timeout=12000)
        await page.wait_for_selector(
            "a[href*='www2.makegoodfood.ca/recipe-card/'], :text('Bonjour'), :text('Vos commandes')",
            timeout=4000,
        )
        return True
    except Exception:
        return False
    finally:
        await page.close()


async def _check_and_dump_failure(page: AsyncPage, reason: str) -> None:
    """Enregistre un screenshot et un dump HTML tronqué pour diagnostic en cas d'échec."""
    ensure_dirs()
    try:
        fail_img = CACHE_DIR / "login_fail.png"
        fail_html = CACHE_DIR / "login_fail.html"
        await page.screenshot(path=str(fail_img), full_page=False)
        html_content = await page.content()
        fail_html.write_text(html_content[:500000], encoding="utf-8")
        print(f"⚠️  Détails de l'échec enregistrés dans {fail_img} et {fail_html}")
    except Exception:
        pass


async def login_with_credentials_async(
    email: str,
    password: str,
    browser: Optional[AsyncBrowser] = None,
    headless: bool = True,
    max_network_retries: int = 2,
) -> tuple[Optional[AsyncBrowser], AsyncContext]:
    """Authentification réelle asynchrone avec validation stricte avant sauvegarde."""
    from playwright.async_api import async_playwright

    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get(
        "login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser="
    )
    timeout_ms = cfg.get("goodfood", {}).get("timeout_ms", 25000)
    probe_url = cfg.get("goodfood", {}).get(
        "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
    )
    state_path = storage_state_path()
    ensure_dirs()

    pw = None
    created_browser = False
    if browser is None:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless,
            args=CHROMIUM_PERF_ARGS,
        )
        created_browser = True

    last_error: Optional[Exception] = None

    for attempt in range(1, max_network_retries + 1):
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="fr-CA",
        )
        await apply_guardrails_async(context)
        page = await context.new_page()

        try:
            await page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

            # 1. Attente du champ email dans le modal React
            email_field = await page.wait_for_selector(
                "[data-testid='email-input-input'], input[name='email'], input[type='email']",
                state="visible",
                timeout=timeout_ms,
            )
            if not email_field:
                raise RuntimeError("Champ email introuvable dans le modal.")
            await email_field.fill(email)

            # 2. Remplissage du mot de passe
            password_field = await page.wait_for_selector(
                "[data-testid='password-input-input'], input[name='password'], input[type='password']",
                state="visible",
                timeout=8000,
            )
            if not password_field:
                raise RuntimeError("Champ mot de passe introuvable dans le modal.")
            await password_field.fill(password)

            # 3. Soumission
            submit = await page.wait_for_selector(
                "[data-testid='login-with-email-cta'], button[type='submit'], button:has-text('Continuer')",
                state="visible",
                timeout=8000,
            )
            if not submit:
                raise RuntimeError("Bouton de connexion introuvable.")

            await submit.click()

            # 4. Attente de la validation réelle (fermeture du modal ou cookie)
            modal_closed = False
            for _ in range(30):
                cookies = await context.cookies()
                cookie_names = {c["name"] for c in cookies}
                if "fbtoken" in cookie_names or "GF3" in cookie_names:
                    modal_closed = True
                    break
                
                # Vérifier si un message d'erreur textuel est apparu dans le formulaire
                error_el = await page.query_selector("[data-testid*='error-message'], .mantine-InputWrapper-error, [data-testid='email-input-error']")
                if error_el and await error_el.is_visible():
                    err_txt = (await error_el.inner_text()).strip()
                    if err_txt:
                        await _check_and_dump_failure(page, err_txt)
                        raise RuntimeError(f"Identifiants Goodfood refusés ({err_txt}). Vérifie GOODFOOD_EMAIL / GOODFOOD_PASSWORD.")
                
                await asyncio.sleep(0.3)

            if not modal_closed:
                # Sonde de secours sur recipe-cards
                modal_closed = await is_logged_in_async(context, probe_url)

            if not modal_closed:
                await _check_and_dump_failure(page, "Session invalide après soumission")
                raise RuntimeError("Échec de connexion : session non établie après soumission du formulaire.")

            # Sauvegarde UNIQUEMENT si validé
            await context.storage_state(path=str(state_path))
            print("✅ Connexion réussie, session sauvegardée.")
            await asyncio.sleep(1.5)
            await page.close()
            return browser, context

        except RuntimeError as e:
            await page.close()
            await context.close()
            if "refusés" in str(e) or "introuvable" in str(e):
                if created_browser and pw is not None:
                    await browser.close()
                    await pw.stop()
                raise
            last_error = e
        except Exception as e:
            await page.close()
            await context.close()
            last_error = e
            if attempt < max_network_retries:
                print(f"⚠️  Tentative de connexion {attempt}/{max_network_retries} échouée ({e}). Nouvel essai...")
                await asyncio.sleep(1.0)

    if created_browser and pw is not None:
        await browser.close()
        await pw.stop()
    raise RuntimeError(f"Échec de connexion à Goodfood après {max_network_retries} tentatives : {last_error}")


async def ensure_session_async(
    browser: Optional[AsyncBrowser] = None,
    headless: bool = True,
) -> tuple[AsyncBrowser, AsyncContext]:
    """Garantit une session authentifiée asynchrone ultra-rapide et vérifiée."""
    from playwright.async_api import async_playwright

    cfg = load_config()
    probe_url = cfg.get("goodfood", {}).get(
        "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
    )
    state_path = storage_state_path()

    if browser is None:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless,
            args=CHROMIUM_PERF_ARGS,
        )

    # Court-circuit P5 : vérification de session
    if is_storage_state_fresh():
        try:
            context = await browser.new_context(
                storage_state=str(state_path),
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="fr-CA",
            )
            await apply_guardrails_async(context)
            if await is_logged_in_async(context, probe_url):
                print("♻️  Session réutilisée avec succès.")
                return browser, context
            await context.close()
        except Exception:
            pass

    email, password = get_credentials()
    print(f"🔐 Connexion Goodfood ({email})...")
    _, context = await login_with_credentials_async(
        email, password, browser=browser, headless=headless
    )
    return browser, context


# --- Wrappers Synchrones pour compatibilité CLI / tests ---

def save_session_manual(headless: bool = False) -> Path:
    """Connexion manuelle dans le navigateur, puis sauvegarde."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get("login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser=")
    state_path = storage_state_path()
    ensure_dirs()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=CHROMIUM_PERF_ARGS)
        context = browser.new_context()
        page = context.new_page()
        apply_guardrails(page)
        page.goto(login_url)
        print(f"\n🔐 Navigateur ouvert sur {login_url}")
        print("   Connecte-toi à la main, puis appuie sur Entrée.\n")
        input("   ✅ Connexion faite ? Entrée pour sauvegarder... ")
        context.storage_state(path=str(state_path))
        browser.close()

    print(f"💾 Session sauvegardée dans {state_path}")
    return state_path


def ensure_session(headless: bool = True):
    """Wrapper synchrone de compatibilité."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, args=CHROMIUM_PERF_ARGS)
    state_path = storage_state_path()
    cfg = load_config()
    probe_url = cfg.get("goodfood", {}).get(
        "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
    )

    if is_storage_state_fresh():
        try:
            context = browser.new_context(storage_state=str(state_path))
            apply_guardrails(context)
            page = context.new_page()
            page.goto(probe_url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_selector(
                "a[href*='www2.makegoodfood.ca/recipe-card/'], :text('Bonjour')",
                timeout=4000,
            )
            page.close()
            print("♻️  Session existante valide.")
            return pw, context
        except Exception:
            pass

    email, password = get_credentials()
    print(f"🔐 Connexion Goodfood ({email})...")
    context = browser.new_context()
    apply_guardrails(context)
    page = context.new_page()
    page.goto(cfg["goodfood"]["login_url"], wait_until="domcontentloaded")
    email_f = page.wait_for_selector("[data-testid='email-input-input'], input[type=email]", timeout=25000)
    email_f.fill(email)
    pwd_f = page.wait_for_selector("[data-testid='password-input-input'], input[type=password]", timeout=10000)
    pwd_f.fill(password)
    sub = page.wait_for_selector("[data-testid='login-with-email-cta'], button[type=submit]", timeout=10000)
    sub.click()
    page.wait_for_selector("a[href*='www2.makegoodfood.ca/recipe-card/'], :text('Bonjour')", timeout=15000)
    context.storage_state(path=str(state_path))
    page.close()
    return pw, context
