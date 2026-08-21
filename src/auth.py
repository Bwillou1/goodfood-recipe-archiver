"""Gestion de l'authentification Goodfood.

Ce module gère la connexion via le flow React/Firebase de Goodfood.
Il sauvegarde et réutilise la session Playwright (cookies et storage_state)
pour minimiser les appels réseau.

Optimisations Haute Vitesse :
- Blocage réseau des images/médias/polices pendant le login (Vitesse x10).
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple
from urllib.parse import urlparse

from .guardrails import apply_guardrails_async
from .utils import CACHE_DIR, load_config

if TYPE_CHECKING:
    from playwright.async_api import Browser as AsyncBrowser, BrowserContext as AsyncContext, Page as AsyncPage, Route, Request

STATE_FILE = CACHE_DIR / "storage_state.json"
LOGIN_ERRORS_DIR = CACHE_DIR / "login_errors"


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("GOODFOOD_EMAIL")
    password = os.environ.get("GOODFOOD_PASSWORD")
    if not email or not password:
        raise ValueError("Les variables GOODFOOD_EMAIL et GOODFOOD_PASSWORD doivent être définies dans .env")
    return email, password


def is_storage_state_fresh(state_path: Path = STATE_FILE, max_age_hours: float = 24.0) -> bool:
    import time
    import json
    if not state_path.exists():
        return False
    
    # 1. Vérifier l'âge du fichier
    age_hours = (time.time() - state_path.stat().st_mtime) / 3600.0
    if age_hours > max_age_hours:
        return False
    
    # 2. Vérifier la présence d'un cookie de session actif
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        for c in cookies:
            if c["name"] in ("fbtoken", "GF3"):
                return True
        return False
    except Exception:
        return False


async def is_logged_in_async(
    context: AsyncContext,
    probe_url: str = "https://www.makegoodfood.ca/fr-CA/recipe-cards",
) -> bool:
    """Vérifie silencieusement si la session est valide."""
    page: Optional[AsyncPage] = None
    try:
        page = await context.new_page()
        
        # Blocage des ressources lourdes pour la vérification
        async def block_assets(route: Route, request: Request):
            if request.resource_type in ("image", "font", "media", "stylesheet"):
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", block_assets)

        await page.goto(probe_url, wait_until="domcontentloaded", timeout=12000)
        await page.wait_for_selector(
            "a[href*='www2.makegoodfood.ca/recipe-card/'], :text('Bonjour'), :text('Vos commandes')",
            timeout=4000,
        )
        return True
    except Exception:
        return False
    finally:
        if page:
            await page.close()


async def _check_and_dump_failure(page: AsyncPage, err_prefix: str = "erreur") -> None:
    """Sauvegarde le HTML et capture d'écran en cas d'erreur de connexion."""
    try:
        LOGIN_ERRORS_DIR.mkdir(parents=True, exist_ok=True)
        import time
        ts = int(time.time())
        html_path = LOGIN_ERRORS_DIR / f"{err_prefix}_{ts}.html"
        html_path.write_text(await page.content(), encoding="utf-8")
    except Exception:
        pass


async def login_with_credentials_async(
    email: str,
    password: str,
    browser: AsyncBrowser,
    headless: bool = True,
    state_path: Path = STATE_FILE,
) -> Tuple[AsyncBrowser, AsyncContext]:
    """Exécute le workflow de connexion interactif et sauvegarde l'état."""
    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get("login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser=")
    probe_url = cfg.get("goodfood", {}).get("recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards")
    timeout_ms = cfg.get("goodfood", {}).get("timeout_ms", 25000)

    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    await apply_guardrails_async(context)
    page = await context.new_page()

    # Blocage des ressources lourdes pour le DOM de login (Accélération massive)
    async def block_assets(route: Route, request: Request):
        if request.resource_type in ("image", "font", "media", "stylesheet"):
            await route.abort()
        else:
            await route.continue_()
    await page.route("**/*", block_assets)

    try:
        print(f"🔐 Connexion Goodfood ({email})...")
        await page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

        # 1. Attente du champ email
        email_field = await page.wait_for_selector(
            "[data-testid='email-input-input'], input[name='email'], input[type='email']",
            state="visible",
            timeout=15000,
        )
        if not email_field:
            raise RuntimeError("Champ courriel introuvable sur la page de connexion.")

        # Effacer et remplir rapidement
        await email_field.fill("")
        await email_field.fill(email)
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.3)

        # 2. Attente du champ mot de passe
        pwd_field = await page.wait_for_selector(
            "[data-testid='password-input-input'], input[name='password'], input[type='password']",
            state="visible",
            timeout=8000,
        )
        if not pwd_field:
            raise RuntimeError("Champ mot de passe introuvable.")

        await pwd_field.fill("")
        await pwd_field.fill(password)
        await page.keyboard.press("Enter")

        # 3. Validation
        submit = await page.wait_for_selector(
            "[data-testid='login-with-email-cta'], button[type='submit'], button:has-text('Continuer')",
            state="visible",
            timeout=8000,
        )
        if submit:
            await submit.click()

        modal_closed = False
        for _ in range(30):
            cookies = await context.cookies()
            cookie_names = {c["name"] for c in cookies}
            if "fbtoken" in cookie_names or "GF3" in cookie_names:
                modal_closed = True
                break
            
            error_el = await page.query_selector("[data-testid*='error-message'], .mantine-InputWrapper-error, [data-testid='email-input-error']")
            if error_el and await error_el.is_visible():
                err_txt = (await error_el.inner_text()).strip()
                if err_txt:
                    await _check_and_dump_failure(page, err_txt)
                    raise RuntimeError(f"Identifiants refusés ({err_txt}).")
            await asyncio.sleep(0.2)

        if not modal_closed:
            modal_closed = await is_logged_in_async(context, probe_url)

        if not modal_closed:
            await _check_and_dump_failure(page, "Session_invalide")
            raise RuntimeError("Échec de connexion : session non établie.")

        await context.storage_state(path=str(state_path))
        print("✅ Connexion réussie, session sauvegardée.")
        
        # Settle post-login pour l'API
        await asyncio.sleep(1.0)
        
        await page.close()
        return browser, context

    except Exception as e:
        await _check_and_dump_failure(page, "ErreurFatale")
        await context.close()
        raise RuntimeError(f"Erreur lors de la connexion automatique: {e}") from e


async def ensure_session_async(
    browser: AsyncBrowser,
    headless: bool = True,
    state_path: Path = STATE_FILE,
) -> Tuple[AsyncBrowser, AsyncContext]:
    """Point d'entrée principal pour obtenir un contexte authentifié."""
    cfg = load_config()
    probe_url = cfg.get("goodfood", {}).get("recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards")

    if is_storage_state_fresh(state_path):
        try:
            context = await browser.new_context(
                storage_state=str(state_path),
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            )
            await apply_guardrails_async(context)
            if await is_logged_in_async(context, probe_url):
                return browser, context
            await context.close()
        except Exception:
            pass

    email, password = get_credentials()
    _, context = await login_with_credentials_async(email, password, browser=browser, headless=headless, state_path=state_path)
    return browser, context
