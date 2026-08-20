"""Garde-fous de sécurité stricts (Strict Read-Only, Anti-Achat & Anti-Altération).

Ce module garantit une protection absolue contre toute modification ou dépense accidentelle :
1. Strict Read-Only : Blocage de TOUTES les mutations vers des endpoints sensibles.
2. Anti-Achat & Panier : Blocage de tout accès au panier, paiement, cartes de crédit, portefeuille.
3. Anti-Altération Abonnements : Blocage de toute modification de forfait, saut/pause de semaine (skip/unskip).
4. Protection Fidélité : Blocage de l'utilisation de crédits, points récompenses, coupons ou rabais.
5. Protection Réputation : Blocage de l'envoi d'avis, notes, commentaires ou formulaires de feedback.
6. Confidentialité & Vitesse : Blocage de tous les traqueurs comportementaux et enregistreurs de session
   (Hotjar, Datadog, Segment, Google Analytics, FullStory, Meta, TikTok, etc.).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

# 🚫 1. URLs et Chemins Sensibles STRICTEMENT INTERDITS
FORBIDDEN_URL_PATTERNS = [
    # --- Panier, Checkout & Paiement ---
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
    r"/stripe",
    r"/paypal",
    
    # --- Abonnements, Pauses & Saut de semaines (/skip, /unskip) ---
    r"/subscription",
    r"/abonnement",
    r"/skip",
    r"/unskip",
    r"/pause",
    r"/resume",
    r"/delivery-schedule",
    r"/horaire-de-livraison",
    r"/my-plan",
    r"/mon-forfait",
    r"/subscriptions/cancel",
    r"/subscriptions/modify",
    r"/orders/cancel",
    r"/orders/edit",
    r"/orders/modify",

    # --- Fidélité, Crédits, Rabais & Récompenses (/rewards, /credits, /loyalty) ---
    r"/rewards",
    r"/recompenses",
    r"/credits",
    r"/loyalty",
    r"/fidelite",
    r"/coupons",
    r"/promo",
    r"/discount",
    r"/rabais",
    r"/gift-card",
    r"/carte-cadeau",
    r"/referrals",
    r"/parrainage",
    r"/balance",
    r"/solde",

    # --- Avis, Évaluations & Feedbacks (/reviews, /feedback, /rating) ---
    r"/reviews",
    r"/avis",
    r"/feedback",
    r"/rating",
    r"/rate",
    r"/evaluer",
    r"/survey",
    r"/sondage",
    r"/comments",
    r"/commentaires",

    # --- Profil & Paramètres sensibles ---
    r"/account/payment",
    r"/account/billing",
    r"/account/edit",
    r"/account/delete",
    r"/user/update",

    # --- Endpoints d'API sensibles ---
    r"/api/.*/checkout",
    r"/api/.*/payment",
    r"/api/.*/order/cancel",
    r"/api/.*/order/edit",
    r"/api/.*/cart",
    r"/api/.*/wallet",
    r"/api/.*/subscription",
    r"/api/.*/skip",
    r"/api/.*/unskip",
    r"/api/.*/review",
    r"/api/.*/rating",
    r"/api/.*/feedback",
]

# 🚫 2. Traceurs tiers, enregistreurs de session et pixels analytiques à bloquer
BLOCKED_TRACKERS = [
    # Outils d'enregistrement de session & APM
    "hotjar.com",
    "hotjar.io",
    "datadoghq.com",
    "browser-intake-datadoghq.com",
    "segment.io",
    "segment.com",
    "fullstory.com",
    "heapanalytics.com",
    "heap.io",
    "sentry.io",
    "amplitude.com",
    "mixpanel.com",
    "crazyegg.com",
    "optimizely.com",
    "newrelic.com",
    "nr-data.net",
    "visualwebsiteoptimizer.com",

    # Google Analytics, Ads & Tag Manager
    "google-analytics.com",
    "analytics.google.com",
    "googletagmanager.com",
    "googleadservices.com",
    "doubleclick.net",

    # Réseaux sociaux & traceurs publicitaires
    "bat.bing.com",
    "connect.facebook.net",
    "analytics.tiktok.com",
    "snapchat.com",
    "ct.pinterest.com",
    "px.ads.linkedin.com",
    "alb.reddit.com",
    "rubiconproject.com",
    "tapad.com",
    "adnxs.com",
    "casalemedia.com",
    "adsrvr.org",
]

FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_URL_PATTERNS), re.IGNORECASE)

# Endpoints autorisés pour requêtes POST (Authentification et Recherche Algolia uniquement)
ALLOWED_POST_PATTERNS = [
    r"identitytoolkit\.googleapis\.com",
    r"firebaseinstallations\.googleapis\.com",
    r"/login",
    r"/api/.*/auth/login",
    r"/api/.*/session",
    r"/algolia/",
    r"algolia\.net",
]
ALLOWED_POST_REGEX = re.compile("|".join(ALLOWED_POST_PATTERNS), re.IGNORECASE)


def is_url_allowed(url: str) -> bool:
    """Vérifie si une URL est sûre et autorisée en lecture seule."""
    if not url:
        return True
        
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Les fichiers statiques Next.js et assets web ne sont jamais des actions sensibles
    if path.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".woff2", ".ico")):
        return True

    if FORBIDDEN_REGEX.search(path):
        return False
        
    return True


def is_tracker(url: str) -> bool:
    """Détecte les pixels publicitaires et enregistreurs de session tiers."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in BLOCKED_TRACKERS)


def is_mutation_allowed(method: str, url: str) -> bool:
    """Autorise uniquement les requêtes de lecture GET ou l'authentification/recherche."""
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    
    # POST / PUT / PATCH / DELETE ne sont permis QUE pour le login ou la recherche
    if ALLOWED_POST_REGEX.search(url):
        return True
        
    return False


def route_guardrail_interceptor(route: Route) -> None:
    """Intercepteur réseau Playwright strict : bloque toute action sensible ou traceur."""
    request = route.request
    url = request.url
    method = request.method.upper()

    # 1. Garde-fou n°1 : Blocage des URLs et sections sensibles
    if not is_url_allowed(url):
        print(f"🛑 [SÉCURITÉ BLOQUÉE] Tentative d'accès à une ressource sensible refusée : {url}")
        route.abort("blockedbyclient")
        return

    # 2. Garde-fou n°2 : Blocage strict des mutations HTTP non autorisées (POST/PUT/DELETE/PATCH)
    if not is_mutation_allowed(method, url):
        print(f"🛑 [MUTATION BLOQUÉE] Requête non autorisée {method} vers : {url}")
        route.abort("blockedbyclient")
        return

    # 3. Garde-fou n°3 : Blocage silencieux des traceurs tiers & enregistreurs de session
    if is_tracker(url):
        route.abort("blockedbyclient")
        return

    route.continue_()


def apply_guardrails(page: Page) -> None:
    """Applique les garde-fous stricts sur une page Playwright."""
    page.route("**/*", route_guardrail_interceptor)
