"""Génération fidèle de la VRAIE fiche recette cartonnée Goodfood en PDF.

Rendu officiel identique au carton papier Goodfood :
- Format A4 Paysage (Landscape) officiel Goodfood (2 pages par fiche).
- Page 1 : Titre officiel, photo HD grand format, ingrédients, temps de cuisson, logo Marché Goodfood.
- Page 2 : Photos des étapes, instructions numérotées, case à cocher [ ], ustensiles requis.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .auth import ensure_session
from .guardrails import apply_guardrails
from .utils import DATA_DIR, RECIPES_DIR, ensure_dirs

RECIPES_PATH = DATA_DIR / "recipes.json"


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


def print_official_card(page, card_url: str, out_path: Path) -> None:
    """Imprime la vraie fiche recette officielle Goodfood (Format Paysage 2 pages)."""
    page.goto(card_url, wait_until="networkidle")
    time.sleep(2)

    # Assure que toutes les images et polices de la fiche sont chargées
    page.evaluate('''() => {
        window.scrollTo(0, document.body.scrollHeight);
    }''')
    time.sleep(1)

    # Impression PDF paysage exacte (comme l'originale Goodfood)
    page.pdf(
        path=str(out_path),
        format="A4",
        landscape=True,
        print_background=True,
        margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
    )


def run(headless: bool = True) -> list[Path]:
    ensure_dirs()
    recipes = load_recipes()
    if not recipes:
        print("⚠️  Aucune recette à imprimer.")
        return []

    pw, context = ensure_session(headless=headless)
    page = context.new_page()
    apply_guardrails(page)

    created: list[Path] = []
    try:
        for i, r in enumerate(recipes, 1):
            card_url = r.get("card_url") or r.get("url")
            if not card_url:
                continue

            slug = r.get("matched_meal") or r.get("title") or f"recette_{i}"
            fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
            fname = fname or f"recette_{i}"
            out = RECIPES_DIR / f"{fname}.pdf"

            print(f"🖨️  Génération de la VRAIE fiche officielle : {slug}")
            print(f"    🔗 {card_url}")
            print_official_card(page, card_url, out)
            created.append(out)
            print(f"    ✅ Fiche Goodfood 2-pages générée : {out.name}")
    finally:
        context.close()
        pw.stop()

    print(f"\n✅ {len(created)} fiche(s) officielle(s) générée(s) dans {RECIPES_DIR}")
    return created
