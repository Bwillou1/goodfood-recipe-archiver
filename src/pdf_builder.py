"""Impression directe et fidèle de la VRAIE page de recette Goodfood en PDF via Playwright.

Aucune modification de mise en page :
- Impression fidèle de la vraie page web Goodfood (CSS officiel, polices, photos, étapes).
- Masquage uniquement de la barre de navigation du site et du footer pour un rendu propre.
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


def print_recipe_page(page, url: str, out_path: Path) -> None:
    """Imprime la vraie page Goodfood en PDF tel quel."""
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    # Masquer uniquement les barres de menu et footer de navigation globale
    page.evaluate('''() => {
        const nav = document.querySelector('header, nav');
        if (nav) nav.style.display = 'none';
        const footers = document.querySelectorAll('footer, [class*="footer"], [class*="Footer"]');
        footers.forEach(f => f.style.display = 'none');
        // Développer les détails si nécessaire
        window.scrollTo(0, document.body.scrollHeight);
    }''')
    time.sleep(1)

    # Impression PDF native Chromium
    page.pdf(
        path=str(out_path),
        format="A4",
        print_background=True,
        margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"},
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
            url = r.get("url")
            if not url:
                continue

            slug = r.get("matched_meal") or r.get("title") or f"recette_{i}"
            fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
            fname = fname or f"recette_{i}"
            out = RECIPES_DIR / f"{fname}.pdf"

            print(f"🖨️  Impression réelle de : {slug}")
            print(f"    🔗 {url}")
            print_recipe_page(page, url, out)
            created.append(out)
            print(f"    ✅ PDF officiel généré : {out.name}")
    finally:
        context.close()
        pw.stop()

    print(f"\n✅ {len(created)} vraie(s) page(s) imprimée(s) dans {RECIPES_DIR}")
    return created
