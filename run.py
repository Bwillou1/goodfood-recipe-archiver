#!/usr/bin/env python3
"""Point d'entrée UNIQUE pour un agent IA — exécute tout le pipeline.

Un agent IA (Claude, Mistral, ...) n'a qu'à lancer :

    python run.py

après avoir :
  1. créé le fichier .env avec les identifiants Goodfood (voir .env.example) ;
  2. déposé la capture de la facture dans data/receipts/ (optionnel si
     data/meals.json existe déjà ou si l'agent fournit la liste des plats).

L'humain ne fait rien d'autre : aucune installation, aucun code à écrire,
aucun cookie à exporter.
"""
from __future__ import annotations

import sys
from pathlib import Path

from src import assembler, auth, finder, ocr_receipt, pdf_builder
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
    # 1. Connexion RÉELLE (identifiants) — crée ou recharge la session
    auth.ensure_session(headless=True)

    # 2. Extraire les plats de la facture (si pas déjà fait)
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

    # 3. Retrouver les recettes sur le site
    finder.run(headless=True)

    # 4. Générer un PDF par recette
    pdf_builder.run()

    # 5. Assembler le PDF final
    final = assembler.run()

    print(f"\n🎉 Terminé ! PDF final : {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
