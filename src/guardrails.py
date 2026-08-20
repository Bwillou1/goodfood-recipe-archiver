"""Garde-fous de sécurité stricts (Strict Read-Only & Anti-Achat).

Ce module garantit :
1. Sécurité absolue : Blocage de tout achat, panier, paiement, modification de commande.
2. Confidentialité & Vitesse : Blocage des traqueurs publicitaires tiers (TikTok, Bing, Meta, etc.).
3. Strict Read-Only : Blocage de toutes les requêtes HTTP de mutation vers des endpoints sensibles.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

# 🚫 URLs et segments de chemins STRICTEMENT INTERDITS (Panier, Paiement, Commandes)
FORBIDDEN_URL_PATTERNS = [
    r"/checkout",
    r"/panier",
    r"/cart",
    r"/payment",
    r"/paiement",
    r"/billing",
    r"/facturation",
    r"/credit-card",
    r"/carte-de-credit",
    r"/wallet",
    r"/portefeuille",
    r"/subscriptions/cancel",
    r"/subscriptions/modify",
    r"/orders/cancel",
    r"/orders/edit",
    r"/orders/modify",
    r"/account/payment",
    r"/account/billing",
    r"/account/edit",
    r"/api/.*/checkout",
    r"/api/.*/payment",
    r"/api/.*/order/cancel",
    r"/api/.*/cart/add",
    r"/api/.*/cart/update",
    r"/api/.*/wallet",
]

# 🚫 Domaines de traqueurs publicitaires tiers à bloquer
BLOCKED_AD_TRACKERS = [
    "bat.bing.com",
    "connect.facebook.net",
    "analytics.tiktok.com",
    "snapchat.com",
    "doubleclick.net",
    "rubiconproject.com",
    "tapad.com",
    "adnxs.com",
    "casalemedia.com",
    "adsrvr.org",
]

FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_URL_PATTERNS), re.IGNORECASE)


def is_url_allowed(url: str) -> bool:
    """Vérifie si une URL est sûre et autorisée en lecture seule."""
    if not url:
        return True
    parsed = urlparse(url)
    path = parsed.path.lower()
    if FORBIDDEN_REGEX.search(path):
        return False
    return True


def is_ad_tracker(url: str) -> bool:
    """Détecte les pixels publicitaires tiers."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in BLOCKED_AD_TRACKERS)


def route_guardrail_interceptor(route: Route) -> None:
    """Intercepteur réseau Playwright : bloque les accès sensibles et accélère le chargement."""
    request = route.request
    url = request.url

    # 1. Vérification de sécurité critique
    if not is_url_allowed(url):
        print(f"🛑 [SÉCURITÉ BLOQUÉE] Tentative d'accès à une ressource sensible refusée : {url}")
        route.abort("blockedbyclient")
        return

    # 2. Accélération : blocage silencieux des pixels publicitaires tiers
    if is_ad_tracker(url):
        route.abort("blockedbyclient")
        return

    route.continue_()


def apply_guardrails(page: Page) -> None:
    """Applique les garde-fous stricts sur une page Playwright."""
    page.route("**/*", route_guardrail_interceptor)
