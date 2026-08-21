#!/usr/bin/env python3
"""Point d'entrée UNIQUE et Haute Performance pour goodfood-recipe-archiver.

Optimisations Globales :
- P1 : Phase B parallèle & asynchrone (asyncio.gather + Semaphore).
- P2 : Navigateur Chromium unique pour tout le cycle de vie.
- P3 : Attentes ciblées Playwright natives (aucun time.sleep aveugle).
- P5 : Court-circuit du cache Phase A (< 24h) et validation locale de session.
- P6 : Flags --meals, --parallel, --refresh, --timing avec rapport d'exécution détaillé.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

from src import assembler, auth, finder, ocr_receipt, pdf_builder
from src.utils import (
    CHROMIUM_PERF_ARGS, DATA_DIR, RECEIPTS_DIR, RECIPES_DIR, ensure_dirs, load_config,
)

MEALS_PATH = DATA_DIR / "meals.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


async def run_pipeline_async(
    meals_arg: Optional[str] = None,
    parallel: int = 3,
    refresh: bool = False,
    show_timing: bool = False,
    headless: bool = True,
) -> int:
    ensure_dirs()
    cfg = load_config()
    timings: dict[str, float] = {}
    t_global_start = time.perf_counter()

    # 1. Résolution des plats (Argument direct, OCR ou data/meals.json)
    target_meals: list[str] = []
    if meals_arg:
        # Séparateurs : pipe |, virgule ,, ou point-virgule ;
        import re
        target_meals = [m.strip() for m in re.split(r"[|,;]", meals_arg) if m.strip()]
        MEALS_PATH.write_text(json.dumps({"meals": target_meals}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📋 {len(target_meals)} plat(s) spécifié(s) via --meals.")
    elif MEALS_PATH.exists():
        target_meals = json.loads(MEALS_PATH.read_text(encoding="utf-8")).get("meals", [])
    else:
        images = [p for p in RECEIPTS_DIR.iterdir() if p.suffix.lower() in IMG_EXTS]
        if images:
            t_ocr = time.perf_counter()
            print(f"\n🧾 Facture détectée : {images[0].name}")
            ocr_receipt.run(image=str(images[0]))
            timings["OCR Facture"] = time.perf_counter() - t_ocr
            target_meals = json.loads(MEALS_PATH.read_text(encoding="utf-8")).get("meals", [])
        else:
            print("\n❌ Aucune facture dans data/receipts/ et aucun data/meals.json.", file=sys.stderr)
            print("   → Passe les plats avec --meals 'Plat 1 | Plat 2' ou dépose une image dans data/receipts/.", file=sys.stderr)
            return 1

    if not target_meals:
        print("\n❌ Aucun plat à rechercher.", file=sys.stderr)
        return 1

    # 2. Lancement du Navigateur Unique (P2)
    async with async_playwright() as pw:
        t_browser = time.perf_counter()
        browser = await pw.chromium.launch(
            headless=headless,
            args=CHROMIUM_PERF_ARGS,
        )
        timings["Lancement Chromium"] = time.perf_counter() - t_browser

        # 3. Phase A : Authentification & Indexation (avec court-circuit P5)
        t_phase_a = time.perf_counter()
        _, auth_context = await auth.ensure_session_async(browser=browser, headless=headless)
        recipes, missing = await finder.find_recipes_async(
            context=auth_context,
            meals=target_meals,
            refresh=refresh,
        )
        await auth_context.close()
        timings["Phase A (Découverte & Matching)"] = time.perf_counter() - t_phase_a

        if not recipes:
            await browser.close()
            print("\n❌ Échec : Aucune recette n'a pu être retrouvée dans l'historique Goodfood.", file=sys.stderr)
            return 1

        # 4. Phase B : Génération Parallèle 100 % Anonyme (P1)
        t_phase_b = time.perf_counter()
        created_pdfs, recipe_timings = await pdf_builder.build_recipes_async(
            browser=browser,
            recipes=recipes,
            parallel=parallel,
        )
        timings["Phase B (Rendu PDF //)"] = time.perf_counter() - t_phase_b
        for r_name, r_dt in recipe_timings.items():
            timings[f"  └─ {r_name[:30]}"] = r_dt

        await browser.close()

    # 5. Phase C : Assemblage du Livre PDF Final (Landscape A4)
    t_phase_c = time.perf_counter()
    final_pdf = assembler.run(pdf_paths=created_pdfs)
    timings["Phase C (Assemblage PDF final)"] = time.perf_counter() - t_phase_c

    t_total = time.perf_counter() - t_global_start
    timings["TOTAL WALL-CLOCK"] = t_total

    print(f"\n🎉 Terminé avec succès ! PDF final disponible : {final_pdf}")

    # Affichage du rapport de performance si --timing est actif
    if show_timing:
        print("\n" + "=" * 56)
        print(" ⏱️  RAPPORT DE PERFORMANCE DÉTAILLÉ (goodfood-archiver)")
        print("=" * 56)
        for phase, dur in timings.items():
            if phase.startswith("  └─"):
                print(f"   {phase:<38} : {dur:.2f} s")
            elif phase == "TOTAL WALL-CLOCK":
                print("-" * 56)
                print(f" 🚀 {phase:<36} : {dur:.2f} s")
            else:
                print(f" • {phase:<36} : {dur:.2f} s")
        print("=" * 56 + "\n")

    if missing:
        print(f"\n⚠️  Attention : {len(missing)} plat(s) n'ont pas pu être associés : {', '.join(missing)}")
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="goodfood-archiver",
        description="Pipeline automatisé & ultra-rapide de récupération des fiches recettes Goodfood.",
    )
    parser.add_argument("--meals", help="Plats séparés par des pipes (ex: 'Plat 1 | Plat 2')")
    parser.add_argument("--parallel", type=int, default=3, help="Nombre d'impressions parallèles (défaut: 3)")
    parser.add_argument("--refresh", action="store_true", help="Forcer le rafraîchissement du cache d'historique")
    parser.add_argument("--timing", action="store_true", help="Afficher les métriques de vitesse détaillées")
    parser.add_argument("--headed", action="store_true", help="Lancer Chromium avec interface visible")

    args = parser.parse_args()

    try:
        return asyncio.run(
            run_pipeline_async(
                meals_arg=args.meals,
                parallel=args.parallel,
                refresh=args.refresh,
                show_timing=args.timing,
                headless=not args.headed,
            )
        )
    except KeyboardInterrupt:
        print("\n⏹️  Interrompu.")
        return 130
    except Exception as e:
        print(f"\n❌ Erreur fatale : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
