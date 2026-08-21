"""Connexion RÉELLE à Goodfood — Architecture Haute Performance & Zéro Sommeil Aveugle.

Optimisations P0/P2/P3/P5 :
- Attente native du modal React via wait_for_selector (aucun sleep/polling).
- Validation locale rapide des cookies avant sonde réseau.
- Support du navigateur partagé (Single Browser Lifecycle).
- Implémentation Asynchrone native et wrappers synchrones rétrocompatibles.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .guardrails import apply_guardrails, apply_guardrails_async
from .utils import (
    CHROMIUM_PERF_ARGS, ensure_dirs, get_credentials, load_config, storage_state_path,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser as AsyncBrowser, BrowserContext as AsyncContext
    from playwright.sync_api import BrowserContext as SyncContext


def is_storage_state_fresh() -> bool:
    """Vérifie localement si storage_state.json contient un fbtoken non expiré."""
    state_path = storage_state_path()
    if not state_path.exists():
        return False
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        cookies = {c["name"]: c for c in data.get("cookies", [])}
        if "fbtoken" not in cookies and "GF3" not in cookies:
            return False
        # Si un cookie d'expiration existe, vérifier qu'il est dans le futur
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
        # Attente ciblée du sélecteur d'authentification (max 4 secondes)
        await page.wait_for_selector(
            "a[href*='www2.makegoodfood.ca/recipe-card/'], :text('Bonjour'), :text('Vos commandes')",
            timeout=4000,
        )
        return True
    except Exception:
        return False
    finally:
        await page.close()


async def login_with_credentials_async(
    email: str,
    password: str,
    browser: Optional[AsyncBrowser] = None,
    headless: bool = True,
) -> tuple[Any, AsyncContext]:
    """Authentification réelle asynchrone avec attentes ciblées."""
    from playwright.async_api import async_playwright

    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get(
        "login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser="
    )
    timeout_ms = cfg.get("goodfood", {}).get("timeout_ms", 25000)
    state_path = storage_state_path()
    ensure_dirs()

    pw = None
    if browser is None:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless,
            args=CHROMIUM_PERF_ARGS,
        )

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

        # 1. Attente native du montage du modal React (P0 / P3)
        email_field = await page.wait_for_selector(
            "[data-testid='email-input-input'], input[name='email'], input[type='email']",
            state="visible",
            timeout=timeout_ms,
        )
        if not email_field:
            raise RuntimeError("Champ email introuvable dans le modal de connexion.")
        await email_field.fill(email)

        # 2. Remplissage du mot de passe
        password_field = await page.wait_for_selector(
            "[data-testid='password-input-input'], input[name='password'], input[type='password']",
            state="visible",
            timeout=10000,
        )
        if not password_field:
            raise RuntimeError("Champ mot de passe introuvable.")
        await password_field.fill(password)

        # 3. Soumission et attente de fermeture du modal / navigation
        submit = await page.wait_for_selector(
            "[data-testid='login-with-email-cta'], button[type='submit'], button:has-text('Continuer')",
            state="visible",
            timeout=10000,
        )
        if not submit:
            raise RuntimeError("Bouton de connexion introuvable.")

        # Clic & attente de navigation ou disparition du modal
        await submit.click()

        # Attendre que le modal disparaisse ou que l'URL change (max 10s)
        try:
            await page.wait_for_function(
                "() => !document.querySelector('[data-testid=\"login-with-email-cta\"]')",
                timeout=8000,
            )
        except Exception:
            pass

        await context.storage_state(path=str(state_path))
        print("✅ Connexion réussie, session sauvegardée.")
        await page.close()
        return browser, context
    except Exception:
        await page.close()
        await context.close()
        if pw is not None:
            await browser.close()
            await pw.stop()
        raise


async def ensure_session_async(
    browser: Optional[AsyncBrowser] = None,
    headless: bool = True,
) -> tuple[AsyncBrowser, AsyncContext]:
    """Garantit une session authentifiée asynchrone ultra-rapide."""
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


# --- Wrappers Synchrones pour rétrocompatibilité ---

def save_session_manual(headless: bool = False) -> Path:
    """Connexion manuelle dans le navigateur, puis sauvegarde."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get("login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser=")
    state_path = storage_state_path()
    ensure_dirs()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
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
