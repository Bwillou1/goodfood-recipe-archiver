"""Garde-fous de sécurité stricts (Hardened Zero-Trust, Anti-Achat & Anti-Traceurs).

Architecture de Sécurité & Filtrage Silencieux :
- Protection hermétique en lecture seule (Strict Read-Only).
- Blocage strict des documents et actions sensibles (Panier, Checkout, Abonnements, Facturation).
- Autorisation des endpoints de lecture bénins (GET /promotion, GET v2/ratings).
- Neutralisation silencieuse des traceurs (Cloudflare RUM, New Relic, TikTok, Google Analytics, Hotjar, etc.).
- Journalisation ciblée : alerte uniquement sur navigation document sensible ou mutation HTTP.
"""
from __future__ import annotations

import asyncio
import inspect
import re
from typing import TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import Route as AsyncRoute
    from playwright.sync_api import Route as SyncRoute

# 🚫 1. URLs et Chemins Sensibles STRICTEMENT INTERDITS (Panier, Checkout, Abonnements, etc.)
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

    # --- Fidélité, Rabais & Récompenses (/coupons, /promo-code, /gift-card) ---
    r"/coupons",
    r"/promo-code",
    r"/code-promo",
    r"/gift-card",
    r"/carte-cadeau",
    r"/referrals",
    r"/parrainage",
    r"/balance",
    r"/solde",

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
]

# Endpoints autorisés en lecture GET uniquement (ex: consultation de promotions ou ratings)
BENIGN_GET_PATTERNS = [
    r"/user/.*/promotion",
    r"/v2/ratings",
    r"/promotion",
]

# 🚫 2. Traceurs tiers, pixels publicitaires et RUM (avortés silencieusement)
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
    "cdn-cgi/rum",
]

FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_URL_PATTERNS), re.IGNORECASE)
BENIGN_GET_REGEX = re.compile("|".join(BENIGN_GET_PATTERNS), re.IGNORECASE)
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


def is_url_allowed(url: str, resource_type: str = "other", method: str = "GET") -> bool:
    """Vérifie si une URL est sûre et autorisée en lecture seule."""
    if not url:
        return True
        
    parsed = urlparse(url)
    path = parsed.path.lower()

    # 1. Traceurs systématiquement bloqués
    if is_tracker(url):
        return False

    # 2. Fichiers statiques toujours autorisés
    if is_static_asset(path):
        return True

    # 3. Endpoints GET autorisés (promotion, ratings)
    if method == "GET" and BENIGN_GET_REGEX.search(path):
        return True

    # 4. Blocage des navigations de document vers les pages sensibles
    if resource_type == "document" and FORBIDDEN_REGEX.search(path):
        return False

    # 5. Blocage général des chemins sensibles
    if FORBIDDEN_REGEX.search(path):
        return False
        
    return True


def is_tracker(url: str) -> bool:
    """Détecte les pixels publicitaires, APM et enregistreurs de session tiers."""
    return bool(BLOCKED_TRACKERS_REGEX.search(url.lower()))


def is_mutation_allowed(method: str, url: str) -> bool:
    """Autorise uniquement les requêtes de lecture GET ou l'authentification/recherche."""
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    
    # POST / PUT / PATCH / DELETE ne sont permis QUE pour le login ou la recherche Algolia
    if ALLOWED_POST_REGEX.search(url):
        return True
        
    return False


def _check_route(url: str, method: str, resource_type: str) -> tuple[bool, bool, str]:
    """Retourne (allowed, should_log_warning, reason) pour le routage.
    
    should_log_warning est True uniquement pour les tentatives de document navigation
    sensible ou les mutations HTTP non autorisées (zéro spam sur les GET XHR ou traceurs).
    """
    parsed = urlparse(url)
    
    # 1. Traceurs & RUM (avortés silencieusement)
    if is_tracker(url):
        return False, False, "tracker"

    # 2. Fichiers statiques autorisés
    if is_static_asset(parsed.path):
        return True, False, "static"

    # 3. Mutations HTTP non autorisées (log d'alerte)
    if not is_mutation_allowed(method, url):
        return False, True, f"mutation_{method}"

    # 4. Endpoints GET de lecture bénins (autorisés)
    if method == "GET" and BENIGN_GET_REGEX.search(parsed.path):
        return True, False, "benign_get"

    # 5. URLs sensibles
    if not is_url_allowed(url, resource_type=resource_type, method=method):
        is_doc = (resource_type == "document")
        return False, is_doc, f"sensitive_{resource_type}"

    return True, False, "ok"


def sync_route_guardrail_interceptor(route: SyncRoute) -> None:
    """Intercepteur pour Playwright synchrone."""
    req = route.request
    allowed, should_log, reason = _check_route(req.url, req.method.upper(), req.resource_type)
    if allowed:
        route.continue_()
    else:
        if should_log:
            print(f"🛑 [SÉCURITÉ BLOQUÉE] {req.method} vers {req.url} ({reason})")
        route.abort("blockedbyclient")


async def async_route_guardrail_interceptor(route: AsyncRoute) -> None:
    """Intercepteur pour Playwright asynchrone."""
    req = route.request
    allowed, should_log, reason = _check_route(req.url, req.method.upper(), req.resource_type)
    if allowed:
        await route.continue_()
    else:
        if should_log:
            print(f"🛑 [SÉCURITÉ BLOQUÉE] {req.method} vers {req.url} ({reason})")
        await route.abort("blockedbyclient")


def apply_guardrails(target: Any) -> None:
    """Applique les garde-fous stricts sur une Page ou un BrowserContext (sync ou async)."""
    if hasattr(target, "route") and inspect.iscoroutinefunction(target.route):
        asyncio.create_task(target.route("**/*", async_route_guardrail_interceptor))
    elif hasattr(target, "route"):
        target.route("**/*", sync_route_guardrail_interceptor)


async def apply_guardrails_async(target: Any) -> None:
    """Applique explicitement les garde-fous sur un objet async Playwright."""
    await target.route("**/*", async_route_guardrail_interceptor)
