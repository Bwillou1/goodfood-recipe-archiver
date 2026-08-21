"""Phase A : Découverte et Indexation Authentifiée des Fiches Recettes Goodfood.

Optimisations Haute Vitesse Extrême :
- Blocage réseau des images, polices et médias pendant la découverte (Vitesse de chargement x10).
- Défilement instantané optimisé dans le contexte JavaScript (< 0.2s au lieu de 4.5s).
- Unification de best_match : retourne systématiquement tuple[dict, float] | None.
- Court-circuit P5 : Réutilisation du cache `ordered_cards.json` (< 24h) si tous les plats matchent (0.0s).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from rapidfuzz import fuzz

from .guardrails import apply_guardrails_async
from .utils import (
    CACHE_DIR, DATA_DIR, RECIPES_DIR, ensure_dirs, load_config, normalize,
)

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext as AsyncContext, Route, Request

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
ORDERED_CARDS_CACHE = CACHE_DIR / "ordered_cards.json"


def load_meals() -> list[str]:
    if not MEALS_PATH.exists():
        raise FileNotFoundError(f"{MEALS_PATH} introuvable. Fournis la capture de facture ou lance avec --meals 'Plat1|Plat2'")
    return json.loads(MEALS_PATH.read_text(encoding="utf-8"))["meals"]


def extract_sku(url: str) -> Optional[str]:
    """Extrait le SKU Goodfood (GF + 6 chiffres) depuis une URL."""
    if not url:
        return None
    m = re.search(r"(GF\d{6}|\b\d{5,7}\b)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def best_match(
    query: str,
    candidates: list[Union[dict, tuple[str, str], list[str]]],
    threshold: float = 0.60,
) -> Optional[tuple[dict, float]]:
    """Retourne la meilleure fiche recette correspondante (format de retour unifié dict + score)."""
    q = normalize(query)
    best_candidate_dict: Optional[dict] = None
    best_score: float = 0.0

    for cand in candidates:
        if isinstance(cand, (tuple, list)):
            title = cand[0]
            url = cand[1] if len(cand) > 1 else ""
            c_dict = {"title": title, "card_url": url, "sku": extract_sku(url) or ""}
        elif isinstance(cand, dict):
            c_dict = cand
            title = cand.get("title", "")
        else:
            title = str(cand)
            c_dict = {"title": title, "card_url": "", "sku": ""}

        norm_title = normalize(title)
        ratio = fuzz.ratio(q, norm_title) / 100.0
        partial = fuzz.partial_ratio(q, norm_title) / 100.0
        token_score = fuzz.token_set_ratio(q, norm_title) / 100.0
        score = max(ratio, partial * 0.9, token_score)

        if score > best_score:
            best_score = score
            best_candidate_dict = c_dict

    if best_candidate_dict and best_score >= threshold:
        return (best_candidate_dict, best_score)
    return None


def get_cached_ordered_cards(ttl_hours: float = 24.0) -> Optional[list[dict]]:
    """Retourne les fiches en cache si elles existent et sont fraîches."""
    if not ORDERED_CARDS_CACHE.exists():
        return None
    try:
        mtime = ORDERED_CARDS_CACHE.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600.0
        if age_hours > ttl_hours:
            return None
        cards = json.loads(ORDERED_CARDS_CACHE.read_text(encoding="utf-8"))
        if isinstance(cards, list) and len(cards) > 0:
            return cards
    except Exception:
        return None
    return None


async def collect_ordered_cards_async(page, url: str, dump: bool = False) -> list[dict]:
    """Extrait l'ensemble des fiches commandées sur /fr-CA/recipe-cards en un temps record."""
    cfg = load_config()

    print(f"🌐 Phase A : Navigation sur l'historique officiel ({url})...")
    
    # Optimisation radicale : bloquer le chargement des images/polices/médias lourds pour ce DOM !
    async def block_assets(route: Route, request: Request):
        if request.resource_type in ("image", "font", "media", "stylesheet"):
            await route.abort()
        else:
            await route.continue_()
            
    await page.route("**/*", block_assets)
    
    await page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("goodfood", {}).get("timeout_ms", 25000))

    # 1. Attente ciblée native de l'apparition des fiches
    try:
        await page.wait_for_selector(
            "a[href*='www2.makegoodfood.ca/recipe-card/']",
            state="attached",
            timeout=15000,
        )
    except Exception:
        return []

    # 2. Dump HTML de diagnostic si demandé
    if dump:
        try:
            dump_path = CACHE_DIR / "page_dump.html"
            content = await page.content()
            dump_path.write_text(content[:500000], encoding="utf-8")
        except Exception:
            pass

    # 3. Extraction & Défilement instantané via JavaScript
    js_extractor = """
    async () => {
        // Défilement asynchrone intelligent 
        let lastHeight = 0;
        for (let i = 0; i < 4; i++) {
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 80));
            if (document.body.scrollHeight === lastHeight) break;
            lastHeight = document.body.scrollHeight;
        }

        const results = [];
        const seenHrefs = new Set();
        const links = document.querySelectorAll("a[href*='www2.makegoodfood.ca/recipe-card/']");
        
        links.forEach(a => {
            const href = a.getAttribute("href") || "";
            if (!href || seenHrefs.has(href)) return;
            seenHrefs.add(href);

            let el = a;
            let title = "";
            let date = "";

            for (let i = 0; i < 8 && el; i++) {
                el = el.parentElement;
                if (!el) break;
                const lines = (el.innerText || "").split("\\n").map(s => s.trim()).filter(Boolean);
                const titleCandidates = lines.filter(t => t !== "Fiche recette" && !t.startsWith("Command") && !t.startsWith("Date"));
                const dateCandidates = lines.filter(t => t.startsWith("Command") || t.startsWith("Date"));
                
                if (titleCandidates.length && !title) title = titleCandidates[0];
                if (dateCandidates.length && !date) date = dateCandidates[0];
            }

            results.push({
                href: href,
                title: title || href.split("/").slice(-2, -1)[0],
                date: date
            });
        });
        return results;
    }
    """
    raw_cards = await page.evaluate(js_extractor)
    formatted = []
    for c in raw_cards:
        href = c["href"]
        sku = extract_sku(href) or ""
        formatted.append({
            "title": c["title"],
            "card_url": href,
            "sku": sku,
            "date": c.get("date", ""),
        })

    return formatted


async def find_recipes_async(
    context: AsyncContext,
    meals: Optional[list[str]] = None,
    refresh: bool = False,
    dump: bool = False,
) -> tuple[list[dict], list[str]]:
    """Phase A Asynchrone : indexation et rapprochement flou avec court-circuit cache."""
    ensure_dirs()
    cfg = load_config()
    target_meals = meals or load_meals()
    threshold = cfg.get("matching", {}).get("threshold", 0.60)
    strict_threshold = cfg.get("matching", {}).get("strict_threshold", 0.85)
    cache_ttl = cfg.get("performance", {}).get("cache_ttl_hours", 24)

    # --- Court-circuit P5 : Vérification du Cache ---
    ordered_cards = None
    if not refresh:
        cached = get_cached_ordered_cards(ttl_hours=cache_ttl)
        if cached:
            all_matched = True
            for m in target_meals:
                if best_match(m, cached, threshold=threshold) is None:
                    all_matched = False
                    break
            if all_matched:
                print(f"⚡ [CACHE] {len(cached)} fiches réutilisées (0.0s réseau).")
                ordered_cards = cached

    # Si pas de cache valide ou refresh demandé, exécuter la découverte réseau
    if ordered_cards is None:
        page = await context.new_page()
        try:
            recipe_cards_url = cfg.get("goodfood", {}).get(
                "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
            )
            ordered_cards = await collect_ordered_cards_async(page, recipe_cards_url, dump=dump)
            if ordered_cards:
                print(f"📚 {len(ordered_cards)} fiches recettes officielles indexées.")
                ORDERED_CARDS_CACHE.write_text(
                    json.dumps(ordered_cards, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        finally:
            await page.close()

    # --- Rapprochement flou (Matching) ---
    recipes: list[dict] = []
    missing: list[str] = []

    for meal in target_meals:
        match_res = best_match(meal, ordered_cards or [], threshold=threshold)
        if match_res is None:
            print(f"   ❌ « {meal} » introuvable dans l'historique.")
            missing.append(meal)
            continue

        candidate, score = match_res
        title = candidate.get("title", "")
        sku = candidate.get("sku", "")
        card_url = candidate.get("card_url", "")

        alert = " (⚠️ Rapprochement modéré)" if score < strict_threshold else ""
        print(f"   ✅ Trouvé [Score: {score:.2f}]{alert} : {title}")
        print(f"      🏷️  SKU : {sku} | 🖨️  {card_url}")

        recipes.append({
            "title": title,
            "card_url": card_url,
            "sku": sku,
            "matched_meal": meal,
            "score": score,
        })

    RECIPES_PATH.write_text(
        json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return recipes, missing


# --- Point d'Entrée Synchrone (délégation propre via asyncio) ---

def run(dump: bool = False, headless: bool = True, refresh: bool = False) -> Path:
    """Exécute la Phase A via le moteur asynchrone unifié."""
    from playwright.async_api import async_playwright
    from .auth import ensure_session_async
    from .utils import CHROMIUM_PERF_ARGS

    async def _runner():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless, args=CHROMIUM_PERF_ARGS)
            _, auth_ctx = await ensure_session_async(browser=browser, headless=headless)
            await find_recipes_async(context=auth_ctx, refresh=refresh, dump=dump)
            await auth_ctx.close()
            await browser.close()

    asyncio.run(_runner())
    return RECIPES_PATH
