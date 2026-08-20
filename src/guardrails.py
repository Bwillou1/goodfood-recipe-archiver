"""Garde-fous de sécurité (Strict Read-Only & Anti-Achat).

Ce module garantit qu'il est techniquement IMPOSSIBLE pour le script ou un agent IA de :
1. Effectuer des achats, valider un panier ou déclencher un paiement.
2. Modifier des commandes existantes ou des abonnements.
3. Accéder ou interagir avec les informations bancaires / cartes de crédit / portefeuille.
4. Envoyer des requêtes de mutation (POST / PUT / DELETE / PATCH) vers des endpoints sensibles.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

# 🚫 URLs et segments de chemins STRICTEMENT INTERDITS
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

# 🚫 Mots-clés de boutons dangereux à bloquer
FORBIDDEN_BUTTON_KEYWORDS = [
    "payer", "pay", "acheter", "buy", "commander", "order", "place order",
    "passer la commande", "ajouter au panier", "add to cart", "confirmer l'achat",
    "valider le panier", "annuler l'abonnement", "cancel subscription",
    "supprimer", "delete", "enregistrer la carte", "save card"
]

FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_URL_PATTERNS), re.IGNORECASE)


def is_url_allowed(url: str) -> bool:
    """Vérifie si une URL est sûre et autorisée en lecture seule."""
    if not url:
        return True
    
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Bloque les URLs contenant un segment interdit
    if FORBIDDEN_REGEX.search(path):
        return False
        
    return True


def route_guardrail_interceptor(route: Route) -> None:
    """Intercepteur réseau Playwright qui bloque instantanément toute tentative d'accès interdit."""
    request = route.request
    url = request.url
    method = request.method.upper()

    # 1. Vérification de l'URL
    if not is_url_allowed(url):
        print(f"🛑 [GARDE-FOU BLOQUÉ] Tentative d'accès à une URL sensible interdite : {url}")
        route.abort("blockedbyclient")
        return

    # 2. Blocage des mutations (POST/PUT/DELETE/PATCH) sauf pour le login initial
    if method in ["POST", "PUT", "DELETE", "PATCH"]:
        # Seule la requête de login est tolérée pour l'authentification
        is_login = any(k in url.lower() for k in ["/login", "/auth", "/session", "/api/v1/auth", "loginmodal"])
        if not is_login:
            print(f"🛑 [GARDE-FOU BLOQUÉ] Requête de mutation {method} interceptée et bloquée : {url}")
            route.abort("blockedbyclient")
            return

    route.continue_()


def apply_guardrails(page: Page) -> None:
    """Applique les garde-fous stricts sur une page Playwright."""
    # Interception de toutes les requêtes réseau
    page.route("**/*", route_guardrail_interceptor)
