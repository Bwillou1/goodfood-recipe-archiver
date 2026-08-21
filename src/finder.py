"""Phase A : Découverte et indexation authentifiée des fiches recettes Goodfood.

Architecture 2 Phases (Recommandation Post-Mortem) :
- Phase A (Authentifiée courte) : Navigation sur /fr-CA/recipe-cards (« Fiches recettes »).
- Extraction par ancrage sur a[href*='www2.makegoodfood.ca/recipe-card/'] et déduction du titre.
- Cache local dans data/cache/ordered_cards.json pour rejouabilité instantanée.
- Rapprochement flou (rapidfuzz) avec journalisation systématique des scores.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from .auth import ensure_session
from .guardrails import apply_guardrails
from .utils import (
    DATA_DIR, RECIPES_DIR, ensure_dirs, load_config, normalize,
)

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
CACHE_DIR = DATA_DIR / "cache"
ORDERED_CARDS_CACHE = CACHE_DIR / "ordered_cards.json"


def load_meals() -> list[str]:
    if not MEALS_PATH.exists():
        raise FileNotFoundError(f"{MEALS_PATH} introuvable. Fournis la capture de facture ou lance : python -m src.cli extract")
    return json.loads(MEALS_PATH.read_text(encoding="utf-8"))["meals"]


def extract_sku(url: str) -> Optional[str]:
    """Extrait le SKU Goodfood (GF + 6 chiffres) depuis une URL."""
    m = re.search(r"(GF\d{6}|\b\d{5,7}\b)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def best_match(query: str, candidates: list[dict], threshold: float = 0.60) -> Optional[tuple[dict, float]]:
    """Retourne la meilleure fiche recette correspondante avec score explicite."""
    q = normalize(query)
    best_candidate: Optional[dict] = None
    best_score: float = 0.0

    for cand in candidates:
        title = cand.get("title", "")
        norm_title = normalize(title)
        
        ratio = fuzz.ratio(q, norm_title) / 100.0
        partial = fuzz.partial_ratio(q, norm_title) / 100.0
        token_score = fuzz.token_set_ratio(q, norm_title) / 100.0
        
        score = max(ratio, partial * 0.9, token_score)

        if score > best_score:
            best_score = score
            best_candidate = cand

    if best_candidate and best_score >= threshold:
        return (best_candidate, best_score)
    return None


def collect_ordered_cards(page, url: str) -> list[dict]:
    """Extrait l'ensemble des fiches réellement commandées sur /fr-CA/recipe-cards."""
    print(f"🌐 Phase A : Navigation sur l'historique officiel ({url})...")
    page.goto(url, wait_until="domcontentloaded")
    
    # 1. Attente active de la présence des fiches
    for _ in range(25):
        if page.locator("a[href*='www2.makegoodfood.ca/recipe-card/']").count() > 0:
            break
        time.sleep(0.5)

    # 2. Défilement dynamique jusqu'à stabilisation complète du compte
    previous_count = -1
    for _ in range(15):
        current_count = page.locator("a[href*='www2.makegoodfood.ca/recipe-card/']").count()
        if current_count > 0 and current_count == previous_count:
            break
        previous_count = current_count
        page.mouse.wheel(0, 5000)
        time.sleep(0.4)

    # 3. Extraction structurée par ancrage sur l'URL www2
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
    raw_cards = page.evaluate(js_extractor)
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


def collect_catalog_cards(page, base_recipes_url: str) -> list[dict]:
    """Secours : extraction depuis le catalogue commercial si /recipe-cards est vide."""
    print(f"🌐 Secours : Exploration du catalogue commercial ({base_recipes_url})...")
    page.goto(base_recipes_url, wait_until="domcontentloaded")
    time.sleep(2)

    toutes = page.locator(':text("Toutes les recettes"), a[href*="category=3MKMain"]').first
    if toutes.count() > 0:
        try:
            toutes.click()
            time.sleep(1)
        except Exception:
            pass

    for _ in range(4):
        page.mouse.wheel(0, 3000)
        time.sleep(0.2)

    cards = []
    seen = set()
    for l in page.locator('a[href*="/product/recipe/"], a[href*="/mealkit/recipes"]').all():
        t = (l.inner_text() or "").strip().replace("\n", " ")
        h = l.get_attribute("href") or ""
        if h.startswith("/"):
            h = "https://www.makegoodfood.ca" + h
        sku = extract_sku(h) or ""
        if sku and sku not in seen:
            seen.add(sku)
            cards.append({
                "title": t or f"Recette {sku}",
                "card_url": f"https://www2.makegoodfood.ca/recipe-card/{sku}/fr",
                "sku": sku,
                "date": "",
            })
    return cards


def run(dump: bool = False, headless: bool = True) -> Path:
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    meals = load_meals()

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    apply_guardrails(page)

    recipes: list[dict] = []
    missing: list[str] = []

    try:
        recipe_cards_url = cfg.get("goodfood", {}).get(
            "recipe_cards_url", "https://www.makegoodfood.ca/fr-CA/recipe-cards"
        )
        ordered_cards = collect_ordered_cards(page, recipe_cards_url)

        if not ordered_cards:
            print("⚠️  Aucune fiche trouvée dans l'historique, bascule sur le catalogue...")
            catalog_url = cfg.get("goodfood", {}).get("catalog_url", "https://www.makegoodfood.ca/fr-CA/mealkit/recipes")
            ordered_cards = collect_catalog_cards(page, catalog_url)

        print(f"\n📚 {len(ordered_cards)} fiches recettes officielles indexées.")

        # Sauvegarde du cache
        ORDERED_CARDS_CACHE.write_text(
            json.dumps(ordered_cards, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        threshold = cfg.get("matching", {}).get("threshold", 0.60)
        strict_threshold = cfg.get("matching", {}).get("strict_threshold", 0.85)

        for meal in meals:
            print(f"\n🔎 Rapprochement pour : « {meal} »")
            match_res = best_match(meal, ordered_cards, threshold=threshold)
            
            if match_res is None:
                print(f"   ❌ Introuvable dans l'historique (seuil {threshold}).")
                missing.append(meal)
                continue

            candidate, score = match_res
            title = candidate["title"]
            sku = candidate["sku"]
            card_url = candidate["card_url"]

            alert = " (⚠️ Rapprochement modéré)" if score < strict_threshold else ""
            print(f"   ✅ Trouvé [Score: {score:.2f}]{alert} : {title}")
            print(f"      🏷️  SKU : {sku}")
            print(f"      🖨️  Fiche officielle : {card_url}")

            recipes.append({
                "title": title,
                "card_url": card_url,
                "sku": sku,
                "matched_meal": meal,
                "score": score,
            })
    finally:
        context.close()
        pw.stop()

    RECIPES_PATH.write_text(
        json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 {len(recipes)} recettes associées prêtes pour la Phase B.")
    if missing:
        print(f"⚠️  {len(missing)} plat(s) introuvable(s) : {', '.join(missing)}")
    return RECIPES_PATH
