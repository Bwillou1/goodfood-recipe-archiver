#!/usr/bin/env python3
"""Point d'entrée UNIQUE pour un agent IA — exécute tout le pipeline de manière ultra-rapide.

Un agent IA (Claude, Mistral, ...) n'a qu'à lancer :

    python run.py

après avoir :
  1. créé le fichier .env avec les identifiants Goodfood (voir .env.example) ;
  2. déposé la capture de la facture dans data/receipts/ (ou créé data/meals.json).

L'humain ne fait rien d'autre : aucune installation, aucun code à écrire,
aucun cookie à exporter.
"""
from __future__ import annotations

import sys
from pathlib import Path

from src import assembler, finder, ocr_receipt, pdf_builder
from src.utils import DATA_DIR, RECEIPTS_DIR, ensure_dirs

MEALS_PATH = DATA_DIR / "meals.json"
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

    # 2. Retrouver les recettes sur le site (avec multi-semaines et bloqueur de traqueurs)
    finder.run(headless=True)

    # 3. Générer un PDF par recette
    created_pdfs = pdf_builder.run()

    # 4. Assembler le PDF final avec page de garde
    final = assembler.run(pdf_paths=created_pdfs)

    print(f"\n🎉 Terminé avec succès ! PDF final disponible : {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
