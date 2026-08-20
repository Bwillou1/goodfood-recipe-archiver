"""Recherche des recettes sur Goodfood à partir des noms de plats.

Pour chaque plat de data/meals.json :
  1. parcourt les menus hebdomadaires disponibles sur Goodfood ;
  2. matche le nom (fuzzy matching rapidfuzz) avec les recettes du catalogue ;
  3. extrait titre, description, image HD, ingrédients et étapes détaillées.

Sortie : data/recipes.json
"""
from __future__ import annotations

import json
import re
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
        norm_title = normalize(title)
        # Ratio complet
        score = fuzz.ratio(q, norm_title) / 100.0
        # Ratio partiel
        partial = fuzz.partial_ratio(q, norm_title) / 100.0
        # Token sort ratio (utile pour 'saumon teriyaki' vs 'saumon au teriyaki')
        token_score = fuzz.token_set_ratio(q, norm_title) / 100.0
        
        combined_score = max(score, partial * 0.9, token_score)
        
        if best is None or combined_score > best[2]:
            best = (title, url, combined_score)
    return best


def scrape_recipe(page, url: str, cfg: dict) -> dict:
    """Ouvre une recette Goodfood et extrait son contenu structuré."""
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(cfg["rate_limit"]["delay_seconds"])

    # 1. Titre
    h1 = page.locator("h1").first
    title = h1.inner_text().strip() if h1.count() > 0 else page.title()
    title = title.replace(" | Marché Goodfood", "").replace(" | Goodfood Market", "").strip()

    # 2. Image principale
    image_url = ""
    for img in page.locator("img").all():
        src = img.get_attribute("src") or ""
        if any(k in src for k in ["cdn.makegoodfood.ca/uploads", "images.ctfassets.net", "cloudfront.net"]) and \
           not any(b in src.lower() for b in ["icon", "logo", "flag", "svg", "pixel", "bing", "google", "facebook"]):
            image_url = src
            break

    body_text = page.locator("body").inner_text()

    # 3. Description
    description = ""
    if "Description" in body_text:
        after_desc = body_text.split("Description", 1)[1]
        for stop_word in ["Contient:", "Ingrédients", "Vous aurez besoin de", "Nutrition"]:
            if stop_word in after_desc:
                after_desc = after_desc.split(stop_word, 1)[0]
        description = " ".join(after_desc.split())

    # 4. Ingrédients
    ingredients: list[str] = []
    if "Ingrédients" in body_text:
        ing_text = body_text.split("Ingrédients", 1)[1]
        for stop_word in ["Vous aurez besoin de", "Nutrition", "Détails de la recette", "Étape 1", "Step 1"]:
            if stop_word in ing_text:
                ing_text = ing_text.split(stop_word, 1)[0]
        raw_lines = [l.strip() for l in ing_text.splitlines() if l.strip()]
        for l in raw_lines:
            if l.lower() in ["4 portions", "(double pour 4 portions)", "2 portions", "ingrédients", "ingredients"]:
                continue
            if len(l) > 2:
                ingredients.append(l)

    # 5. Étapes de préparation
    steps: list[str] = []
    step_pattern = re.compile(
        r'((?:Étape|Step)\s+\d+:\s*[^\n]+)\n((?:(?!\n(?:Étape|Step)\s+\d+:|\nApprendre a nous connaitre|\nFinances|\nAbout us)[\s\S])*)',
        re.IGNORECASE,
    )
    for m in step_pattern.finditer(body_text):
        step_title = m.group(1).strip()
        step_body = " ".join(m.group(2).split())
        steps.append(f"{step_title} — {step_body}")

    return {
        "title": title,
        "url": url,
        "image": image_url,
        "ingredients": ingredients,
        "steps": steps,
        "description": description,
    }


def collect_all_candidates(page, base_recipes_url: str) -> list[tuple[str, str]]:
    """Parcourt les différentes semaines et onglets pour trouver toutes les recettes disponibles."""
    print(f"🌐 Navigation sur {base_recipes_url}")
    page.goto(base_recipes_url, wait_until="domcontentloaded")
    time.sleep(2)

    candidates_dict: dict[str, str] = {}

    # Trouve les sélecteurs de semaines (ex: août 30, sept 6, etc.)
    date_tabs = page.locator('div[class*="min-w-[92px]"], div[class*="week"], div[class*="Date"]').all()
    num_weeks = max(1, len(date_tabs))

    for idx in range(num_weeks):
        try:
            tabs = page.locator('div[class*="min-w-[92px]"], div[class*="week"], div[class*="Date"]').all()
            if tabs and idx < len(tabs):
                tab = tabs[idx]
                tab_text = tab.inner_text().replace('\n', ' ').strip()
                print(f"   📅 Semaine {idx+1}/{len(tabs)} : {tab_text}")
                tab.click()
                time.sleep(1.5)

            # Clique sur 'Toutes les recettes'
            toutes = page.locator(':text("Toutes les recettes"), :text("All Recipes")').first
            if toutes.count() > 0:
                try:
                    toutes.click()
                    time.sleep(1)
                except Exception:
                    pass

            # Scroll pour déclencher le lazy-loading
            for _ in range(4):
                page.mouse.wheel(0, 2500)
                time.sleep(0.4)

            # Récupère tous les liens de recettes
            links = page.locator('a[href*="/recipe/"], a[href*="/product/recipe/"]').all()
            for l in links:
                t = (l.inner_text() or l.get_attribute("title") or l.get_attribute("aria-label") or "").strip()
                t = " ".join(t.split())
                h = l.get_attribute("href") or ""
                if h.startswith("/"):
                    h = "https://www.makegoodfood.ca" + h
                if t and h and h not in candidates_dict:
                    candidates_dict[h] = t
        except Exception as e:
            print(f"   ⚠️  Avertissement semaine {idx+1}: {e}")

    return [(title, url) for url, title in candidates_dict.items()]


def run(dump: bool = False, headless: bool = True) -> Path:
    ensure_dirs()
    cfg = load_config()
    meals = load_meals()

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    recipes: list[dict] = []
    missing: list[str] = []

    try:
        base_recipes_url = "https://www.makegoodfood.ca/fr-CA/recipes"
        candidates = collect_all_candidates(page, base_recipes_url)
        print(f"\n📚 {len(candidates)} recettes trouvées au total dans le catalogue Goodfood.")

        if dump:
            dump_path = RECIPES_DIR / "page_dump.html"
            dump_path.write_text(page.content(), encoding="utf-8")
            print(f"   🗂️  HTML sauvegardé dans {dump_path}.")

        threshold = cfg.get("matching", {}).get("threshold", 0.65)

        for meal in meals:
            print(f"\n🔎 Recherche du plat : « {meal} »")
            match = best_match(meal, candidates)
            if match is None or match[2] < threshold:
                print(f"   ❌ Introuvable (meilleur score {match[2]:.2f} si disponible < seuil {threshold}).")
                missing.append(meal)
                continue

            title, url, score = match
            print(f"   ✅ Trouvé : {title} (score: {score:.2f})")
            print(f"      🔗 URL : {url}")
            try:
                recipe = scrape_recipe(page, url, cfg)
                recipe["matched_meal"] = meal
                recipes.append(recipe)
            except Exception as e:
                print(f"   ⚠️  Erreur d'extraction : {e}")
                recipes.append({
                    "title": title, "url": url, "matched_meal": meal,
                    "ingredients": [], "steps": [], "image": "", "description": "",
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
