"""Phase A : Découverte et Indexation Authentifiée des Fiches Recettes Goodfood.

Optimisations Haute Performance (P0 / P3 / P5) :
- Court-circuit P5 : Réutilisation du cache `ordered_cards.json` (< 24h) si tous les plats matchent (0.0s réseau).
- Attentes ciblées Playwright natives (P0/P3) sans aucun sleep fixe.
- Défilement intelligent stabilisé pour capturer l'ensemble des fiches sans temps mort.
- Rapprochement flou rapide (rapidfuzz) avec journalisation systématique des scores.
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
    from playwright.async_api import BrowserContext as AsyncContext

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
ORDERED_CARDS_CACHE = CACHE_DIR / "ordered_cards.json"


def load_meals() -> list[str]:
    if not MEALS_PATH.exists():
        raise FileNotFoundError(f"{MEALS_PATH} introuvable. Fournis la capture de facture ou lance avec --meals 'Plat1|Plat2'")
    return json.loads(MEALS_PATH.read_text(encoding="utf-8"))["meals"]


def extract_sku(url: str) -> Optional[str]:
    """Extrait le SKU Goodfood (GF + 6 chiffres) depuis une URL."""
    m = re.search(r"(GF\d{6}|\b\d{5,7}\b)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def best_match(
    query: str,
    candidates: list[Union[dict, tuple[str, str], list[str]]],
    threshold: float = 0.60,
) -> Optional[Any]:
    """Retourne la meilleure fiche recette correspondante (supporte dicts ou tuples)."""
    q = normalize(query)
    best_candidate: Any = None
    best_score: float = 0.0
    is_tuple_format = False

    for cand in candidates:
        if isinstance(cand, (tuple, list)):
            is_tuple_format = True
            title = cand[0]
        elif isinstance(cand, dict):
            title = cand.get("title", "")
        else:
            title = str(cand)

        norm_title = normalize(title)
        ratio = fuzz.ratio(q, norm_title) / 100.0
        partial = fuzz.partial_ratio(q, norm_title) / 100.0
        token_score = fuzz.token_set_ratio(q, norm_title) / 100.0
        score = max(ratio, partial * 0.9, token_score)

        if score > best_score:
            best_score = score
            best_candidate = cand

    if best_candidate and best_score >= threshold:
        if is_tuple_format and isinstance(best_candidate, (tuple, list)):
            return (best_candidate[0], best_candidate[1] if len(best_candidate) > 1 else "", best_score)
        return (best_candidate, best_score)
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


async def collect_ordered_cards_async(page, url: str) -> list[dict]:
    """Extrait l'ensemble des fiches commandées sur /fr-CA/recipe-cards de façon asynchrone."""
    cfg = load_config()
    politeness = cfg.get("rate_limit", {}).get("delay_seconds", 0.3)

    print(f"🌐 Phase A : Navigation sur l'historique officiel ({url})...")
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

    # 2. Défilement asynchrone stabilisé
    previous_count = -1
    for _ in range(15):
        current_count = await page.locator("a[href*='www2.makegoodfood.ca/recipe-card/']").count()
        if current_count > 0 and current_count == previous_count:
            break
        previous_count = current_count
        await page.mouse.wheel(0, 5000)
        await asyncio.sleep(politeness)

    # 3. Extraction structurée par ancrage JavaScript
    js_extractor = """
    () => {
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
            # Vérifier si tous les plats matchent dans le cache
            all_matched = True
            for m in target_meals:
                if best_match(m, cached, threshold=threshold) is None:
                    all_matched = False
                    break
            if all_matched:
                print(f"⚡ [CACHE] {len(cached)} fiches réutilisées depuis le cache local (0.0s réseau).")
                ordered_cards = cached

    # Si pas de cache valide ou refresh demandé, exécuter la découverte réseau
    if ordered_cards is None:
        page = await context.new_page()
        try:
            recipe_cards_url = cfg.get("goodfood", {}).get(
                "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
            )
            ordered_cards = await collect_ordered_cards_async(page, recipe_cards_url)
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
        match_res = best_match(meal, ordered_cards, threshold=threshold)
        if match_res is None:
            print(f"   ❌ « {meal} » introuvable dans l'historique.")
            missing.append(meal)
            continue

        candidate, score = match_res
        title = candidate["title"] if isinstance(candidate, dict) else candidate[0]
        sku = candidate.get("sku", "") if isinstance(candidate, dict) else extract_sku(candidate[1]) or ""
        card_url = candidate.get("card_url", "") if isinstance(candidate, dict) else candidate[1]

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


# --- Wrapper Synchrone ---

def run(dump: bool = False, headless: bool = True, refresh: bool = False) -> Path:
    """Point d'entrée synchrone pour compatibilité."""
    from .auth import ensure_session
    ensure_dirs()
    cfg = load_config()
    meals = load_meals()
    threshold = cfg.get("matching", {}).get("threshold", 0.60)
    cache_ttl = cfg.get("performance", {}).get("cache_ttl_hours", 24)

    # Court-circuit cache
    if not refresh:
        cached = get_cached_ordered_cards(ttl_hours=cache_ttl)
        if cached:
            all_matched = all(best_match(m, cached, threshold=threshold) is not None for m in meals)
            if all_matched:
                print(f"⚡ [CACHE] {len(cached)} fiches réutilisées depuis le cache.")
                recipes = []
                missing = []
                for m in meals:
                    res = best_match(m, cached, threshold=threshold)
                    if res:
                        c, s = res
                        recipes.append({
                            "title": c["title"], "card_url": c["card_url"],
                            "sku": c["sku"], "matched_meal": m, "score": s
                        })
                    else:
                        missing.append(m)
                RECIPES_PATH.write_text(json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2), encoding="utf-8")
                return RECIPES_PATH

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    try:
        url = cfg.get("goodfood", {}).get("recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("a[href*='www2.makegoodfood.ca/recipe-card/']", timeout=15000)
        ordered_cards = asyncio.run(collect_ordered_cards_async(page, url))
        ORDERED_CARDS_CACHE.write_text(json.dumps(ordered_cards, ensure_ascii=False, indent=2), encoding="utf-8")
        recipes = []
        missing = []
        for m in meals:
            match_res = best_match(m, ordered_cards, threshold=threshold)
            if match_res:
                c, s = match_res
                title = c["title"] if isinstance(c, dict) else c[0]
                url_c = c["card_url"] if isinstance(c, dict) else c[1]
                sku_c = c.get("sku", "") if isinstance(c, dict) else extract_sku(url_c) or ""
                recipes.append({"title": title, "card_url": url_c, "sku": sku_c, "matched_meal": m, "score": s})
            else:
                missing.append(m)
        RECIPES_PATH.write_text(json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        context.close()
        pw.stop()
    return RECIPES_PATH
