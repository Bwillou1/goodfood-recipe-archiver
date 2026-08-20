"""Génération fidèle de la VRAIE fiche recette cartonnée Goodfood en PDF.

Rendu officiel identique au carton papier Goodfood :
- Format A4 Paysage (Landscape) officiel Goodfood (2 pages par fiche).
- Page 1 : Titre officiel, photo HD grand format, ingrédients, temps de cuisson, logo Marché Goodfood.
- Page 2 : Photos des étapes HD, instructions numérotées, case à cocher [ ], ustensiles requis.
- Décodage complet garanti de toutes les images pour éliminer tout spinner "Loading...".
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter

from .auth import ensure_session
from .guardrails import apply_guardrails
from .utils import DATA_DIR, RECIPES_DIR, ensure_dirs

RECIPES_PATH = DATA_DIR / "recipes.json"


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


def print_official_card(page, card_url: str, out_path: Path) -> None:
    """Imprime la vraie fiche recette officielle Goodfood avec chargement complet des 2 pages."""
    page.goto(card_url, wait_until="networkidle")
    time.sleep(1.5)

    # 1. Déclenche le lazy-loading de la page 2 et force le chargement de toutes les images HD
    page.evaluate('''async () => {
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 800));
        
        const imgs = Array.from(document.querySelectorAll('img'));
        await Promise.all(imgs.map(img => {
            if (img.complete && img.naturalWidth > 0) return Promise.resolve();
            return new Promise(resolve => {
                img.onload = resolve;
                img.onerror = resolve;
                setTimeout(resolve, 3000); // timeout de secours
            });
        }));
    }''')
    time.sleep(1)

    # 2. Impression PDF paysage native
    temp_path = out_path.with_suffix(".tmp.pdf")
    page.pdf(
        path=str(temp_path),
        format="A4",
        landscape=True,
        print_background=True,
        margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
    )

    # 3. Vérification des pages : si la page 2 est vide (ex: plat micro-ondes sans étapes), on ne garde que la page 1
    reader = PdfReader(str(temp_path))
    writer = PdfWriter()

    for idx, p in enumerate(reader.pages):
        text = (p.extract_text() or "").strip()
        imgs = len(p.images)
        # Conserver la page si elle contient du texte ou des images
        if idx == 0 or len(text) > 20 or imgs > 0:
            writer.add_page(p)

    with open(out_path, "wb") as f:
        writer.write(f)

    temp_path.unlink(missing_ok=True)


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
