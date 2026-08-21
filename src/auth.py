"""Connexion RÉELLE à Goodfood avec identifiants (email + mot de passe).

Sécurité & Robustesse garanties :
- Garde-fous réseau stricts actifs (Strict Read-Only & Anti-Achat).
- Attente sur condition (polling dynamique) pour le modal React Next.js (?loginModal=email).
- Validation de session par la PRÉSENCE sur https://www.makegoodfood.ca/fr-CA/recipe-cards.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

from .guardrails import apply_guardrails
from .utils import ensure_dirs, get_credentials, load_config, storage_state_path

DEFAULT_LOGIN_SELECTORS = {
    "email": [
        "[data-testid='email-input-input']",
        "input[type=email]",
        "input[name=email]",
        "input[autocomplete=email]",
    ],
    "password": [
        "[data-testid='password-input-input']",
        "input[type=password]",
        "input[name=password]",
        "input[autocomplete=current-password]",
    ],
    "submit": [
        "[data-testid='login-with-email-cta']",
        "button[type=submit]",
        "button:has-text('Se connecter')",
        "button:has-text('Continuer')",
    ],
    "captcha": [
        "iframe[src*='recaptcha']",
        "iframe[src*='hcaptcha']",
        "div[class*='g-recaptcha']",
        "[class*='captcha']",
    ],
    "auth_markers": [
        "a[href*='www2.makegoodfood.ca/recipe-card/']",
        ":text('Vos commandes')",
        ":text('Fiches recettes')",
        ":text('Bonjour')",
    ],
}


def _first_visible(page, selectors: list[str]):
    """Retourne le premier élément visible parmi une liste de sélecteurs."""
    for s in selectors:
        try:
            loc = page.locator(s)
            if loc.count() > 0:
                el = loc.first
                if el.is_visible():
                    return el
        except Exception:
            continue
    return None


def _selectors(cfg: dict) -> dict:
    merged = {k: list(v) for k, v in DEFAULT_LOGIN_SELECTORS.items()}
    for k, v in (cfg.get("goodfood", {}).get("login_selectors", {}) or {}).items():
        if v:
            merged[k] = v if isinstance(v, list) else [v]
    return merged


def login_with_credentials(email: str, password: str, headless: bool = True):
    """Vrai login : remplit le formulaire React monté dynamiquement et valide la session."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()
    login_url = cfg.get("goodfood", {}).get("login_url", "https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser=")
    sel = _selectors(cfg)
    state_path = storage_state_path()
    ensure_dirs()

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="fr-CA",
    )
    page = context.new_page()
    apply_guardrails(page)

    try:
        page.goto(login_url, wait_until="domcontentloaded", timeout=cfg.get("goodfood", {}).get("timeout_ms", 30000))

        # --- 1. Attente dynamique du montage du modal par React (jusqu'à 30 s) ---
        email_field = None
        for _ in range(30):
            email_field = _first_visible(page, sel["email"])
            if email_field is not None:
                break
            time.sleep(0.5)

        if email_field is None:
            raise RuntimeError(
                "Champ email introuvable dans le modal de connexion. "
                "Vérifie la connexion réseau ou les sélecteurs dans config/config.yaml."
            )
        email_field.fill(email)

        # --- 2. Champ mot de passe ---
        password_field = _first_visible(page, sel["password"])
        if password_field is None:
            raise RuntimeError("Champ mot de passe introuvable dans le modal.")
        password_field.fill(password)

        # --- 3. Détection CAPTCHA de sécurité ---
        captcha = _first_visible(page, sel["captcha"])
        if captcha is not None:
            raise RuntimeError(
                "CAPTCHA détecté sur la page de connexion : la connexion automatique est bloquée. "
                "Utilise `python -m src.cli auth --manual` une fois."
            )

        # --- 4. Soumission ---
        submit = _first_visible(page, sel["submit"])
        if submit is None:
            raise RuntimeError("Bouton de connexion introuvable.")
        submit.click()

        # Attente de la validation et redirection
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        time.sleep(1.5)

        context.storage_state(path=str(state_path))
        print("✅ Connexion réussie, session sauvegardée.")
        return pw, context
    except Exception:
        browser.close()
        pw.stop()
        raise


def is_logged_in(context, probe_url: str) -> bool:
    """Vérifie la session par la PRÉSENCE d'un contenu strictement réservé au compte connecté."""
    cfg = load_config()
    sel = _selectors(cfg)
    page = context.new_page()
    apply_guardrails(page)
    try:
        page.goto(probe_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)
        # Preuve par la présence
        for marker in sel["auth_markers"]:
            if page.locator(marker).count() > 0:
                return True
        return False
    except Exception:
        return False
    finally:
        page.close()


def ensure_session(headless: bool = True):
    """Garantit une session valide : vérifie la présence sur recipe-cards, sinon connexion propre."""
    cfg = load_config()
    probe_url = cfg.get("goodfood", {}).get("recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards")
    state_path = storage_state_path()

    if state_path.exists():
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(storage_state=str(state_path))
            if is_logged_in(context, probe_url):
                print("♻️  Session existante toujours valide sur Goodfood.")
                return pw, context
            context.close()
            browser.close()
            pw.stop()
        except Exception:
            pass
        print("⚠️  Session expirée ou jeton manquant, réauthentification...")

    email, password = get_credentials()
    print(f"🔐 Connexion réelle à Goodfood ({email})...")
    return login_with_credentials(email, password, headless=headless)
