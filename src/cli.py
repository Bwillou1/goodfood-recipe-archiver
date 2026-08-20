"""Point d'entrée CLI — toutes les commandes du projet.

Usage :
  python -m src.cli auth                 # connexion + sauvegarde session
  python -m src.cli extract --image X    # OCR de la facture
  python -m src.cli extract --list A B   # liste manuelle
  python -m src.cli find                 # retrouver les recettes
  python -m src.cli build                # générer les PDF
  python -m src.cli assemble             # fusionner en PDF final
  python -m src.cli all --image X        # tout le pipeline
  python -m src.cli demo                 # PDF d'exemple (sans compte)
"""
from __future__ import annotations

import argparse
import sys

from . import assembler, auth, finder, ocr_receipt, pdf_builder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="goodfood-archiver",
        description="Récupère tes recettes Goodfood et les compile en PDF.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="Connexion réelle + sauvegarde de session")
    p_auth.add_argument("--manual", action="store_true",
                        help="Connexion manuelle dans le navigateur (secours si CAPTCHA)")

    p_extract = sub.add_parser("extract", help="Extraire les plats de la facture")
    p_extract.add_argument("--image", help="Capture d'écran de la facture")
    p_extract.add_argument("--list", nargs="+", help="Liste manuelle de plats")
    p_extract.add_argument("--lang", help="Langue Tesseract (défaut: config)")

    p_find = sub.add_parser("find", help="Retrouver les recettes sur Goodfood")
    p_find.add_argument("--dump", action="store_true", help="Sauvegarder le HTML pour inspection")
    p_find.add_argument("--headed", action="store_true", help="Afficher le navigateur")

    sub.add_parser("build", help="Générer un PDF par recette")
    sub.add_parser("assemble", help="Assembler en PDF final")

    p_all = sub.add_parser("all", help="Pipeline complet")
    p_all.add_argument("--image", help="Capture d'écran de la facture")
    p_all.add_argument("--list", nargs="+", help="Liste manuelle de plats")
    p_all.add_argument("--headed", action="store_true", help="Afficher le navigateur")

    sub.add_parser("demo", help="Générer un PDF d'exemple (sans compte)")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "auth":
            if args.manual:
                auth.save_session_manual(headless=False)
            else:
                auth.ensure_session(headless=True)
        elif args.cmd == "extract":
            ocr_receipt.run(image=args.image, meal_list=args.list, lang=args.lang)
        elif args.cmd == "find":
            finder.run(dump=args.dump, headless=not args.headed)
        elif args.cmd == "build":
            pdf_builder.run()
        elif args.cmd == "assemble":
            assembler.run()
        elif args.cmd == "all":
            ocr_receipt.run(image=args.image, meal_list=args.list)
            finder.run(headless=not args.headed)
            pdf_builder.run()
            assembler.run()
        elif args.cmd == "demo":
            from .demo import run_demo
            run_demo()
    except FileNotFoundError as e:
        print(f"\n❌ {e}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹️  Interrompu.")
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
