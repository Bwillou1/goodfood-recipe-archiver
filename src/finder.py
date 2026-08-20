"""Recherche des recettes sur Goodfood à partir des noms de plats.

Pour chaque plat de data/meals.json :
  1. va sur la page de recherche/liste des recettes ;
  2. matche le nom (fuzzy) avec les liens disponibles ;
  3. ouvre la recette et extrait titre, ingrédients, étapes, image, lien.

Sortie : data/recipes.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from .auth import ensure_session
from .utils import (
    DATA_DIR, RECIPES_DIR, ensure_dirs, load_config, normalize,
)

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"


def load_meals() -> list[str]:
    if not MEALS_PATH.exists():
        raise FileNotFoundError(f"{MEALS_PATH} introuvable. Lance d'abord : python -m src.cli extract")
    return json.loads(MEALS_PATH.read_text(encoding="utf-8"))["meals"]


def best_match(query: str, candidates: list[tuple[str, str]]) -> Optional[tuple[str, str, float]]:
    """Retourne le meilleur candidat (titre, url, score) pour une requête."""
    q = normalize(query)
    best: Optional[tuple[str, str, float]] = None
    for title, url in candidates:
        score = fuzz.ratio(q, normalize(title)) / 100.0
        # Bonus si le titre contient la requête (ou l'inverse)
        partial = fuzz.partial_ratio(q, normalize(title)) / 100.0
        score = max(score, partial)
        if best is None or score > best[2]:
            best = (title, url, score)
    return best


def scrape_recipe(page, url: str, cfg: dict) -> dict:
    """Ouvre une recette et en extrait le contenu."""
    sel = cfg["goodfood"]["selectors"]
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(cfg["rate_limit"]["delay_seconds"])

    def _text(selector: str) -> list[str]:
        loc = page.locator(selector)
        if loc.count() == 0:
            return []
        return [e.inner_text().strip() for e in loc.all() if e.inner_text().strip()]

    title = page.title()
    # Priorité au h1, sinon le <title>
    h1 = _text(sel["recipe_title"])
    if h1:
        title = h1[0]

    ingredients = _text(sel["recipe_ingredients"])
    steps = _text(sel["recipe_steps"])

    image_url = ""
    img = page.locator(sel["recipe_image"]).first
    if img.count() > 0:
        image_url = img.get_attribute("src") or ""

    return {
        "title": title,
        "url": url,
        "image": image_url,
        "ingredients": ingredients,
        "steps": steps,
        "description": page.locator('meta[name="description"]').get_attribute("content") or "",
    }


def run(dump: bool = False, headless: bool = True) -> Path:
    ensure_dirs()
    cfg = load_config()
    meals = load_meals()

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    recipes: list[dict] = []
    missing: list[str] = []

    try:
        recipes_url = cfg["goodfood"]["recipes_url"]
        print(f"🌐 Ouverture de {recipes_url}")
        page.goto(recipes_url, wait_until="domcontentloaded")
        time.sleep(cfg["rate_limit"]["delay_seconds"])

        # Récupère tous les liens de recettes visibles
        sel = cfg["goodfood"]["selectors"]["recipe_link"]
        links = page.locator(sel)
        candidates: list[tuple[str, str]] = []
        for i in range(links.count()):
            el = links.nth(i)
            title = (el.inner_text() or el.get_attribute("title") or el.get_attribute("aria-label") or "").strip()
            href = el.get_attribute("href") or ""
            if title and href:
                # Résout les URLs relatives
                if href.startswith("/"):
                    href = cfg["goodfood"]["base_url"] + href
                candidates.append((title, href))

        print(f"   {len(candidates)} liens de recettes trouvés.")

        if dump:
            dump_path = RECIPES_DIR / "page_dump.html"
            dump_path.write_text(page.content(), encoding="utf-8")
            print(f"   🗂️  HTML sauvegardé dans {dump_path} (inspecte-le pour ajuster les sélecteurs).")
            if not candidates:
                print("   ⚠️  Aucun lien trouvé — les sélecteurs sont probablement à adapter.")

        for meal in meals:
            print(f"\n🔎 Recherche : {meal}")
            match = best_match(meal, candidates)
            if match is None or match[2] < cfg["matching"]["threshold"]:
                print(f"   ❌ Introuvable (score max insuffisant).")
                missing.append(meal)
                continue
            title, url, score = match
            print(f"   ✅ {title} (score {score:.2f})")
            try:
                recipe = scrape_recipe(page, url, cfg)
                recipe["matched_meal"] = meal
                recipes.append(recipe)
            except Exception as e:  # noqa: BLE001
                print(f"   ⚠️  Erreur d'extraction : {e}")
                recipes.append({"title": title, "url": url, "matched_meal": meal,
                                "ingredients": [], "steps": [], "image": "", "description": ""})
    finally:
        context.close()
        pw.stop()

    RECIPES_PATH.write_text(
        json.dumps({"recipes": recipes, "missing": missing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 {len(recipes)} recettes trouvées, {len(missing)} introuvables → {RECIPES_PATH}")
    return RECIPES_PATH
