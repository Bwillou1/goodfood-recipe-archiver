"""Connexion RÉELLE à Goodfood avec identifiants (email + mot de passe).

Contrairement à une simple réutilisation de cookie (qui oblige l'humain à
exporter sa session depuis son navigateur), ce module fait un **vrai login** :
il remplit le formulaire de connexion avec les identifiants fournis, puis
soumet réellement la requête au site.

Une fois connecté, la session est sauvegardée (cookies/storage_state.json)
et réutilisée tant qu'elle reste valide ; sinon on se reconnecte automatiquement.

Les identifiants viennent du fichier `.env` (voir `.env.example`) :
    GOODFOOD_EMAIL=ton@email.com
    GOODFOOD_PASSWORD=ton_mot_de_passe
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

from .utils import ensure_dirs, get_credentials, load_config, storage_state_path

# Sélecteurs par défaut — surchargés par config/config.yaml (login_selectors)
DEFAULT_LOGIN_SELECTORS = {
    "email": [
        "input[type=email]", "input[name=email]", "input[name=username]",
        "input[name=login]", "#email", "input[autocomplete=email]",
    ],
    "password": [
        "input[type=password]", "input[name=password]", "#password",
        "input[autocomplete=current-password]",
    ],
    "submit": [
        "button[type=submit]", "input[type=submit]",
        "button:has-text('Se connecter')", "button:has-text('Log in')",
        "button:has-text('Connexion')", "button:has-text('Sign in')",
    ],
    "captcha": [
        "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
        "div[class*='g-recaptcha']", "[class*='captcha']",
    ],
    "logged_out": [
        "a:has-text('Se connecter')", "a:has-text('Log in')",
        "a:has-text('Sign in')",
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
        except Exception:  # noqa: BLE001
            continue
    return None


def _selectors(cfg: dict) -> dict:
    merged = {k: list(v) for k, v in DEFAULT_LOGIN_SELECTORS.items()}
    for k, v in (cfg.get("goodfood", {}).get("login_selectors", {}) or {}).items():
        if v:
            merged[k] = v if isinstance(v, list) else [v]
    return merged


def login_with_credentials(email: str, password: str, headless: bool = True):
    """Vrai login : remplit le formulaire et soumet réellement au site."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()
    login_url = cfg["goodfood"]["login_url"]
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

    try:
        page.goto(login_url, wait_until="domcontentloaded",
                  timeout=cfg["goodfood"]["timeout_ms"])
        time.sleep(2)

        # --- Champ email ---
        email_field = _first_visible(page, sel["email"])
        if email_field is None:
            raise RuntimeError(
                "Champ email introuvable. Les sélecteurs de connexion sont "
                "probablement à adapter dans config/config.yaml (login_selectors)."
            )
        email_field.fill(email)

        # --- Champ mot de passe ---
        password_field = _first_visible(page, sel["password"])
        if password_field is None:
            raise RuntimeError(
                "Champ mot de passe introuvable. Vérifie login_selectors.email/password."
            )
        password_field.fill(password)

        # --- Détection CAPTCHA (bloquant pour une vraie connexion) ---
        captcha = _first_visible(page, sel["captcha"])
        if captcha is not None:
            raise RuntimeError(
                "CAPTCHA détecté sur la page de connexion : la connexion 100% "
                "automatique est bloquée par le site. Solutions : réessaie plus "
                "tard, ou utilise `python -m src.cli auth --manual` une fois."
            )

        # --- Soumission ---
        submit = _first_visible(page, sel["submit"])
        if submit is None:
            raise RuntimeError("Bouton de connexion introuvable. Vérifie login_selectors.submit.")
        submit.click()

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)

        # --- Vérification du succès ---
        still_logged_out = _first_visible(page, sel["logged_out"]) is not None
        on_login_page = "login" in page.url.lower() or "signin" in page.url.lower()
        if still_logged_out and on_login_page:
            # Cherche un éventuel message d'erreur
            error = page.locator("[class*='error'], [role='alert']").first
            msg = error.inner_text().strip() if error.count() > 0 else "identifiants refusés ?"
            raise RuntimeError(f"Échec de connexion ({msg}). Vérifie GOODFOOD_EMAIL / GOODFOOD_PASSWORD.")

        context.storage_state(path=str(state_path))
        print("✅ Connexion réussie, session sauvegardée.")
        return pw, context
    except Exception:
        browser.close()
        pw.stop()
        raise


def save_session_manual(headless: bool = False) -> Path:
    """Solution de secours : connexion manuelle dans le navigateur, puis sauvegarde."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()
    login_url = cfg["goodfood"]["login_url"]
    state_path = storage_state_path()
    ensure_dirs()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)
        print(f"\n🔐 Navigateur ouvert sur {login_url}")
        print("   Connecte-toi à la main, puis reviens ici et appuie sur Entrée.\n")
        input("   ✅ Connexion faite ? Entrée pour sauvegarder... ")
        context.storage_state(path=str(state_path))
        browser.close()

    print(f"💾 Session sauvegardée dans {state_path}")
    return state_path


def load_session(headless: bool = True):
    """Crée un contexte Playwright à partir de la session sauvegardée."""
    from playwright.sync_api import sync_playwright

    state_path = storage_state_path()
    if not state_path.exists():
        raise FileNotFoundError(
            f"Session introuvable ({state_path}). Lance d'abord : python -m src.cli auth"
        )
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(state_path))
    return pw, context


def is_logged_in(context, base_url: str) -> bool:
    """Vérifie si la session est encore valide."""
    cfg = load_config()
    sel = _selectors(cfg)
    page = context.new_page()
    try:
        page.goto(base_url, wait_until="domcontentloaded",
                  timeout=cfg["goodfood"]["timeout_ms"])
        logged_out = _first_visible(page, sel["logged_out"]) is not None
        return not logged_out
    finally:
        page.close()


def ensure_session(headless: bool = True):
    """Garantit une session valide : recharge celle en cache, sinon vraie connexion."""
    state_path = storage_state_path()
    if state_path.exists():
        pw, context = load_session(headless=headless)
        if is_logged_in(context, load_config()["goodfood"]["base_url"]):
            print("♻️  Session existante toujours valide, réutilisée.")
            return pw, context
        context.close()
        pw.stop()
        print("⚠️  Session expirée, reconnexion...")

    email, password = get_credentials()
    print(f"🔐 Connexion réelle à Goodfood ({email})...")
    return login_with_credentials(email, password, headless=headless)
