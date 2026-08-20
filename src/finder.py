"""Recherche des recettes sur Goodfood et extraction des IDs de fiches officielles.

Sécurité & Vitesse garanties :
- Mode Strict Read-Only avec garde-fous actifs.
- Récupère l'identifiant Goodfood (ex: GF105585, GF105597) pour chaque plat.
- Construit l'URL officielle de la fiche recette cartonnée (https://www2.makegoodfood.ca/recipe-card/...).
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


def load_meals() -> list[str]:
    if not MEALS_PATH.exists():
        raise FileNotFoundError(f"{MEALS_PATH} introuvable. Lance d'abord : python -m src.cli extract")
    return json.loads(MEALS_PATH.read_text(encoding="utf-8"))["meals"]


def extract_recipe_id(url: str) -> Optional[str]:
    """Extrait l'ID Goodfood de type GF123456 ou 123456 depuis l'URL."""
    m = re.search(r"(GF\d+|\b\d{5,7}\b)", url, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def best_match(query: str, candidates: list[tuple[str, str]]) -> Optional[tuple[str, str, float]]:
    """Retourne le meilleur candidat (titre, url, score) pour une requête."""
    q = normalize(query)
    best: Optional[tuple[str, str, float]] = None
    for title, url in candidates:
        norm_title = normalize(title)
        score = fuzz.ratio(q, norm_title) / 100.0
        partial = fuzz.partial_ratio(q, norm_title) / 100.0
        token_score = fuzz.token_set_ratio(q, norm_title) / 100.0
        
        combined_score = max(score, partial * 0.9, token_score)
        
        if best is None or combined_score > best[2]:
            best = (title, url, combined_score)
    return best


def get_official_card_url(page, product_url: str, lang: str = "fr") -> str:
    """Trouve l'URL de la vraie fiche recette officielle Goodfood."""
    recipe_id = extract_recipe_id(product_url)
    if recipe_id:
        return f"https://www2.makegoodfood.ca/recipe-card/{recipe_id}/{lang}"
    return product_url


def collect_all_candidates(page, base_recipes_url: str) -> list[tuple[str, str]]:
    """Parcourt les semaines actives et onglets pour trouver toutes les recettes disponibles."""
    print(f"🌐 Navigation sur {base_recipes_url}")
    page.goto(base_recipes_url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector('a[href*="product/recipe"], a[href*="recipes?category"]', timeout=12000)
    except Exception:
        time.sleep(2)

    candidates_dict: dict[str, str] = {}

    # 1. Clique sur Toutes les recettes si visible
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

    for l in page.locator('a[href*="/product/recipe/"]').all():
        t = (l.inner_text() or "").strip().replace("\n", " ")
        h = l.get_attribute("href") or ""
        if h.startswith("/"):
            h = "https://www.makegoodfood.ca" + h
        if t and h:
            candidates_dict[h] = t

    # 2. Navigation sur les onglets des autres semaines
    date_spans = page.locator('span:has-text("août"), span:has-text("sept"), span:has-text("oct"), span:has-text("nov")').all()
    for span in date_spans:
        try:
            span.locator("..").click()
            time.sleep(1)
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(0.2)
            for l in page.locator('a[href*="/product/recipe/"]').all():
                t = (l.inner_text() or "").strip().replace("\n", " ")
                h = l.get_attribute("href") or ""
                if h.startswith("/"):
                    h = "https://www.makegoodfood.ca" + h
                if t and h:
                    candidates_dict[h] = t
        except Exception:
            pass

    return [(title, url) for url, title in candidates_dict.items()]


def run(dump: bool = False, headless: bool = True) -> Path:
    ensure_dirs()
    cfg = load_config()
    meals = load_meals()

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    apply_guardrails(page)
    recipes: list[dict] = []
    missing: list[str] = []

    try:
        base_recipes_url = cfg.get("goodfood", {}).get("recipes_url", "https://www.makegoodfood.ca/fr-CA/recipes")
        candidates = collect_all_candidates(page, base_recipes_url)
        print(f"\n📚 {len(candidates)} recettes indexées dans le catalogue Goodfood.")

        if dump:
            dump_path = RECIPES_DIR / "page_dump.html"
            dump_path.write_text(page.content(), encoding="utf-8")
            print(f"   🗂️  HTML sauvegardé dans {dump_path}.")

        threshold = cfg.get("matching", {}).get("threshold", 0.60)

        for meal in meals:
            print(f"\n🔎 Recherche du plat : « {meal} »")
            match = best_match(meal, candidates)
            if match is None or match[2] < threshold:
                best_score_str = f"{match[2]:.2f}" if match else "0.00"
                print(f"   ❌ Introuvable (meilleur score : {best_score_str} < seuil {threshold}).")
                missing.append(meal)
                continue

            title, product_url, score = match
            official_card_url = get_official_card_url(page, product_url, lang="fr")
            recipe_id = extract_recipe_id(product_url) or ""

            print(f"   ✅ Trouvé : {title} (score: {score:.2f})")
            print(f"      🏷️  ID Goodfood : {recipe_id}")
            print(f"      🖨️  Fiche officielle : {official_card_url}")

            recipes.append({
                "title": title,
                "product_url": product_url,
                "card_url": official_card_url,
                "recipe_id": recipe_id,
                "matched_meal": meal,
            })
    finally:
        context.close()
        pw.stop()

    RECIPES_PATH.write_text(
        json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 {len(recipes)} recettes enregistrées dans {RECIPES_PATH}")
    if missing:
        print(f"⚠️  {len(missing)} plat(s) introuvable(s) : {', '.join(missing)}")
    return RECIPES_PATH
