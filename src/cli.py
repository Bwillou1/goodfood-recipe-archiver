"""Point d'entrée CLI — toutes les commandes du projet Goodfood Recipe Archiver.

Usage :
  python -m src.cli auth                 # connexion + sauvegarde session
  python -m src.cli extract --image X    # OCR de la facture
  python -m src.cli extract --list A B   # liste manuelle de plats
  python -m src.cli find                 # retrouver les recettes (Phase A)
  python -m src.cli build                # imprimer les PDF en parallèle (Phase B)
  python -m src.cli sku GF105044         # rejouabilité instantanée pour un SKU (3s)
  python -m src.cli assemble             # fusionner en PDF final (Phase C)
  python -m src.cli all --timing         # tout le pipeline avec chronométrage
  python -m src.cli demo                 # PDF d'exemple (sans compte)
"""
from __future__ import annotations

import argparse
import sys

from . import assembler, auth, finder, ocr_receipt, pdf_builder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="goodfood-archiver",
        description="Récupère tes recettes Goodfood et les compile en PDF officiel.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="Connexion réelle + sauvegarde de session")
    p_auth.add_argument("--manual", action="store_true",
                        help="Connexion manuelle dans le navigateur (secours si CAPTCHA)")

    p_extract = sub.add_parser("extract", help="Extraire les plats de la facture")
    p_extract.add_argument("--image", help="Capture d'écran de la facture")
    p_extract.add_argument("--list", nargs="+", help="Liste manuelle de plats")
    p_extract.add_argument("--lang", help="Langue Tesseract (défaut: fra)")

    p_find = sub.add_parser("find", help="Phase A : Retrouver les recettes (espace /recipe-cards)")
    p_find.add_argument("--dump", action="store_true", help="Sauvegarder le HTML pour diagnostic")
    p_find.add_argument("--refresh", action="store_true", help="Forcer le rafraîchissement du cache")
    p_find.add_argument("--headed", action="store_true", help="Afficher le navigateur")

    p_build = sub.add_parser("build", help="Phase B : Générer les PDF officiels en parallèle")
    p_build.add_argument("--parallel", type=int, default=3, help="Nombre de tâches parallèles (défaut: 3)")

    p_sku = sub.add_parser("sku", help="Télécharger directement une fiche par SKU (ex: GF105044)")
    p_sku.add_argument("sku", help="Identifiant Goodfood (ex: GF105044)")
    p_sku.add_argument("--lang", default="fr", choices=["fr", "en"], help="Langue de la fiche")

    sub.add_parser("assemble", help="Phase C : Assembler en PDF final avec table des matières")

    p_all = sub.add_parser("all", help="Pipeline complet (Phase A + Phase B + Phase C)")
    p_all.add_argument("--image", help="Capture d'écran de la facture")
    p_all.add_argument("--list", nargs="+", help="Liste manuelle de plats")
    p_all.add_argument("--meals", help="Plats séparés par | (ex: 'Plat 1 | Plat 2')")
    p_all.add_argument("--parallel", type=int, default=3, help="Nombre de tâches parallèles")
    p_all.add_argument("--refresh", action="store_true", help="Forcer rafraîchissement cache")
    p_all.add_argument("--timing", action="store_true", help="Afficher chronométrage détaillé")
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
            finder.run(dump=args.dump, headless=not args.headed, refresh=args.refresh)
        elif args.cmd == "build":
            pdf_builder.run(parallel=args.parallel)
        elif args.cmd == "sku":
            pdf_builder.build_single_sku(args.sku, lang=args.lang)
        elif args.cmd == "assemble":
            assembler.run()
        elif args.cmd == "all":
            from run import run_pipeline_async
            import asyncio
            meals_param = args.meals or (" | ".join(args.list) if args.list else None)
            return asyncio.run(
                run_pipeline_async(
                    meals_arg=meals_param,
                    parallel=args.parallel,
                    refresh=args.refresh,
                    show_timing=args.timing,
                    headless=not args.headed,
                )
            )
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
