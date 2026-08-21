"""Garde-fous de sécurité stricts (Hardened Zero-Trust, Anti-Achat & Anti-Traceurs).

Optimisation Haute Performance (P4) :
- Filtrage rapide par domaines bloqués (traceurs, pixels publicitaires, APM).
- Whitelist prioritaire des fichiers statiques et domaines CDN Goodfood pour zéro latence d'hydratation.
- Préservation intégrale de toutes les interdictions strictes (Panier, Checkout, Abonnements, Mutations HTTP).
- Support unifié Synchrone et Asynchrone Playwright.
"""
from __future__ import annotations

import asyncio
import inspect
import re
from typing import TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext as AsyncContext, Page as AsyncPage, Route as AsyncRoute
    from playwright.sync_api import BrowserContext as SyncContext, Page as SyncPage, Route as SyncRoute

# 🚫 1. URLs et Chemins Sensibles STRICTEMENT INTERDITS (Panier, Abonnements, Fidélité, Avis, etc.)
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
    r"/subscriptions/pause",
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

# 🚫 2. Traceurs tiers, enregistreurs de session et pixels publicitaires
BLOCKED_TRACKERS = [
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
    "google-analytics.com",
    "analytics.google.com",
    "googletagmanager.com",
    "googleadservices.com",
    "doubleclick.net",
    "bat.bing.com",
    "connect.facebook.net",
    "analytics.tiktok.com",
    "tiktokw.us",
    "snapchat.com",
    "ct.pinterest.com",
    "px.ads.linkedin.com",
    "alb.reddit.com",
    "rubiconproject.com",
    "tapad.com",
    "adnxs.com",
    "casalemedia.com",
    "adsrvr.org",
    "mczbf.com",
    "justone.ai",
]

FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_URL_PATTERNS), re.IGNORECASE)
BLOCKED_TRACKERS_REGEX = re.compile("|".join(re.escape(t) for t in BLOCKED_TRACKERS), re.IGNORECASE)

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

# Extensions de fichiers statiques autorisées sans restriction
STATIC_EXTENSIONS = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".webp",
    ".svg", ".woff", ".woff2", ".ttf", ".eot", ".ico", ".map",
)


def is_static_asset(path: str) -> bool:
    """Vérifie si la requête cible un fichier statique."""
    clean_path = path.split("?")[0].lower()
    return clean_path.endswith(STATIC_EXTENSIONS) or "/_next/static/" in clean_path


def is_url_allowed(url: str, resource_type: str = "other") -> bool:
    """Vérifie si une URL est sûre et autorisée en lecture seule."""
    if not url:
        return True
        
    parsed = urlparse(url)
    path = parsed.path.lower()

    # 1. Règle intelligente : Fichiers statiques toujours autorisés
    if is_static_asset(path):
        return True

    # 2. Blocage des navigations de document vers les pages sensibles
    if resource_type == "document" and FORBIDDEN_REGEX.search(path):
        return False

    # 3. Blocage général des chemins sensibles
    if FORBIDDEN_REGEX.search(path):
        return False
        
    return True


def is_tracker(url: str) -> bool:
    """Détecte les pixels publicitaires et enregistreurs de session tiers."""
    return bool(BLOCKED_TRACKERS_REGEX.search(url.lower()))


def is_mutation_allowed(method: str, url: str) -> bool:
    """Autorise uniquement les requêtes de lecture GET ou l'authentification/recherche."""
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    
    # POST / PUT / PATCH / DELETE ne sont permis QUE pour le login ou la recherche Algolia
    if ALLOWED_POST_REGEX.search(url):
        return True
        
    return False


def _check_route(url: str, method: str, resource_type: str) -> tuple[bool, str]:
    """Retourne (allowed, reason) pour le routage."""
    parsed = urlparse(url)
    
    # 1. Fichiers statiques autorisés immédiatement
    if is_static_asset(parsed.path):
        return True, "static"

    # 2. Garde-fou traceurs (abort silencieux et immédiat)
    if is_tracker(url):
        return False, "tracker"

    # 3. Garde-fou URLs sensibles
    if not is_url_allowed(url, resource_type=resource_type):
        return False, f"sensitive_url ({resource_type})"

    # 4. Garde-fou mutations HTTP
    if not is_mutation_allowed(method, url):
        return False, f"mutation_{method}"

    return True, "ok"


def sync_route_guardrail_interceptor(route: SyncRoute) -> None:
    """Intercepteur pour Playwright synchrone."""
    req = route.request
    allowed, reason = _check_route(req.url, req.method.upper(), req.resource_type)
    if allowed:
        route.continue_()
    else:
        if reason.startswith("sensitive") or reason.startswith("mutation"):
            print(f"🛑 [SÉCURITÉ BLOQUÉE] {req.method} vers {req.url} ({reason})")
        route.abort("blockedbyclient")


async def async_route_guardrail_interceptor(route: AsyncRoute) -> None:
    """Intercepteur pour Playwright asynchrone."""
    req = route.request
    allowed, reason = _check_route(req.url, req.method.upper(), req.resource_type)
    if allowed:
        await route.continue_()
    else:
        if reason.startswith("sensitive") or reason.startswith("mutation"):
            print(f"🛑 [SÉCURITÉ BLOQUÉE] {req.method} vers {req.url} ({reason})")
        await route.abort("blockedbyclient")


def apply_guardrails(target: Any) -> None:
    """Applique les garde-fous stricts sur une Page ou un BrowserContext (sync ou async)."""
    # Détection si target est async ou sync
    if hasattr(target, "route") and inspect.iscoroutinefunction(target.route):
        # Async target
        asyncio.create_task(target.route("**/*", async_route_guardrail_interceptor))
    elif hasattr(target, "route"):
        # Sync target
        target.route("**/*", sync_route_guardrail_interceptor)


async def apply_guardrails_async(target: Any) -> None:
    """Applique explicitement les garde-fous sur un objet async Playwright."""
    await target.route("**/*", async_route_guardrail_interceptor)
