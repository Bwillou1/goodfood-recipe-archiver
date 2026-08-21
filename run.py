#!/usr/bin/env python3
"""Point d'entrée UNIQUE pour un agent IA — Architecture 2 Phases & Exécution Robuste.

Un agent IA (Claude, Mistral, ...) n'a qu'à lancer :
    python run.py

Pipeline d'exécution :
1. Extraction des plats (OCR facture ou meals.json)
2. Phase A : Découverte authentifiée sur /fr-CA/recipe-cards
3. Phase B : Téléchargement anonyme & rendu officiel sur www2.makegoodfood.ca
4. Phase C : Assemblage du livre PDF final (Goodfood_recettes.pdf)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src import assembler, finder, ocr_receipt, pdf_builder
from src.utils import DATA_DIR, RECEIPTS_DIR, ensure_dirs

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def main() -> int:
    ensure_dirs()

    try:
        return _pipeline()
    except FileNotFoundError as e:
        print(f"\n❌ {e}\n", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"\n❌ {e}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹️  Interrompu.")
        return 130


def _pipeline() -> int:
    # 1. Extraire les plats de la facture (si pas déjà fait)
    if not MEALS_PATH.exists():
        images = [p for p in RECEIPTS_DIR.iterdir() if p.suffix.lower() in IMG_EXTS]
        if images:
            print(f"\n🧾 Facture détectée : {images[0].name}")
            ocr_receipt.run(image=str(images[0]))
        else:
            print("\n⚠️  Aucune facture dans data/receipts/ et pas de data/meals.json.")
            print("    → Dépose la capture de ta facture dans data/receipts/ puis relance `python run.py`,")
            print("      ou fournis directement la liste des plats (data/meals.json ou --list).")
            return 1

    # 2. Phase A : Découverte authentifiée sur /fr-CA/recipe-cards
    finder.run(headless=True)

    # Vérification des résultats de la Phase A
    recipes_data = json.loads(RECIPES_PATH.read_text(encoding="utf-8")) if RECIPES_PATH.exists() else {}
    recipes = recipes_data.get("recipes", [])
    missing = recipes_data.get("missing", [])

    if not recipes:
        print("\n❌ Échec : Aucune recette n'a pu être retrouvée dans l'historique Goodfood.", file=sys.stderr)
        return 1

    # 3. Phase B : Génération anonyme des PDF officiels 2 pages
    created_pdfs = pdf_builder.run(headless=True)

    # 4. Phase C : Assemblage du livre PDF final
    final = assembler.run(pdf_paths=created_pdfs)

    print(f"\n🎉 Terminé avec succès ! PDF final disponible : {final}")
    
    if missing:
        print(f"\n⚠️  Attention : {len(missing)} plat(s) n'ont pas pu être associés : {', '.join(missing)}")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
