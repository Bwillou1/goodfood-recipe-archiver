"""Phase B : Rendu 100 % Anonyme et Génération Parallèle des PDF Officiels Goodfood.

Optimisations P0/P1/P3/P5 :
- Parallélisation asynchrone native via asyncio.gather et asyncio.Semaphore (P1).
- Zéro sommeil aveugle : wait_until="domcontentloaded" + promesse de décodage d'images (plafond dur 3 s) (P0/P3).
- Contexte anonyme partagé (zéro fuite de session vers www2).
- Cache disque des fiches déjà générées (> 30 Ko) (P5).
- Tolérance aux pannes avec réessais et back-off exponentiel avec jitter.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pypdf import PdfReader, PdfWriter

from .guardrails import apply_guardrails_async
from .utils import (
    CHROMIUM_PERF_ARGS, DATA_DIR, RECIPES_DIR, ensure_dirs, load_config,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser as AsyncBrowser, BrowserContext as AsyncContext, Page as AsyncPage

RECIPES_PATH = DATA_DIR / "recipes.json"


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


async def print_card_page_async(
    context: AsyncContext,
    card_url: str,
    out_path: Path,
    max_retries: int = 3,
) -> Path:
    """Imprime une fiche recette de façon asynchrone avec validation et réessais."""
    temp_path = out_path.with_suffix(".tmp.pdf")

    for attempt in range(1, max_retries + 1):
        page: Optional[AsyncPage] = None
        try:
            page = await context.new_page()
            await page.goto(card_url, wait_until="domcontentloaded", timeout=20000)

            # Déclenchement rapide du scroll et décodage de toutes les images HD (max 3s)
            js_script = """
            async () => {
                window.scrollTo(0, document.body.scrollHeight);
                const imgs = Array.from(document.querySelectorAll('img'));
                await Promise.all(imgs.map(img => {
                    if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                        setTimeout(resolve, 2500);
                    });
                }));
            }
            """
            await page.evaluate(js_script)

            # Impression PDF native Chromium A4 Paysage
            await page.pdf(
                path=str(temp_path),
                format="A4",
                landscape=True,
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            )

            await page.close()
            page = None

            # Validation & Nettoyage des pages blanches orphelines
            reader = PdfReader(str(temp_path))
            writer = PdfWriter()

            for idx, p in enumerate(reader.pages):
                text = (p.extract_text() or "").strip()
                imgs = len(p.images)
                if idx == 0 or len(text) > 20 or imgs > 0:
                    writer.add_page(p)

            with open(out_path, "wb") as f:
                writer.write(f)

            temp_path.unlink(missing_ok=True)

            # Contrôle de taille
            size = out_path.stat().st_size
            if size < 25000:
                raise ValueError(f"Fichier trop petit ({size} octets), possible rendu incomplet.")

            return out_path
        except Exception as e:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
            delay = (2 ** attempt) + random.uniform(0.1, 0.5)
            if attempt == max_retries:
                temp_path.unlink(missing_ok=True)
                raise RuntimeError(f"Échec d'impression pour {card_url} ({e})") from e
            await asyncio.sleep(delay)

    return out_path


async def _worker(
    sem: asyncio.Semaphore,
    context: AsyncContext,
    recipe: dict,
    index: int,
    total: int,
    results: list[Path],
    timings: dict[str, float],
) -> None:
    """Tâche concurrente pour une fiche recette."""
    card_url = recipe.get("card_url") or recipe.get("url")
    if not card_url:
        return

    slug = recipe.get("matched_meal") or recipe.get("title") or f"recette_{index}"
    fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
    fname = fname or f"recette_{index}"
    out_path = RECIPES_DIR / f"{fname}.pdf"

    # Cache hit : fichier déjà valide
    if out_path.exists() and out_path.stat().st_size > 30000:
        print(f"⚡ [CACHE] Fiche déjà archivée : {out_path.name} ({out_path.stat().st_size // 1024} Ko)")
        results.append(out_path)
        return

    async with sem:
        t0 = time.perf_counter()
        print(f"🖨️  Phase B [//] [{index}/{total}] : {slug}")
        await print_card_page_async(context, card_url, out_path)
        dt = time.perf_counter() - t0
        timings[slug] = dt
        print(f"    ✅ PDF officiel généré en {dt:.1f}s : {out_path.name} ({out_path.stat().st_size // 1024} Ko)")
        results.append(out_path)


async def build_recipes_async(
    browser: AsyncBrowser,
    recipes: Optional[list[dict]] = None,
    parallel: int = 3,
) -> tuple[list[Path], dict[str, float]]:
    """Génère l'ensemble des PDF de fiches de façon concurrente dans un contexte anonyme."""
    ensure_dirs()
    target_recipes = recipes or load_recipes()
    if not target_recipes:
        return [], {}

    # Contexte anonyme vierge (zéro cookies, garde-fous stricts)
    anon_context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    await apply_guardrails_async(anon_context)

    sem = asyncio.Semaphore(parallel)
    results: list[Path] = []
    timings: dict[str, float] = {}

    try:
        tasks = [
            _worker(sem, anon_context, r, i, len(target_recipes), results, timings)
            for i, r in enumerate(target_recipes, 1)
        ]
        await asyncio.gather(*tasks)
    finally:
        await anon_context.close()

    # Conserver l'ordre original des recettes
    ordered_results = []
    for r in target_recipes:
        slug = r.get("matched_meal") or r.get("title") or ""
        fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
        expected_path = RECIPES_DIR / f"{fname}.pdf"
        if expected_path in results:
            ordered_results.append(expected_path)

    return ordered_results or results, timings


def build_single_sku(sku: str, lang: str = "fr", out_dir: Optional[Path] = None, headless: bool = True) -> Path:
    """Téléchargement direct synchrone d'un SKU unique (5s)."""
    from playwright.sync_api import sync_playwright
    cfg = load_config()
    out_dir = out_dir or RECIPES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    card_url_template = cfg.get("goodfood", {}).get("card_url_template", "https://www2.makegoodfood.ca/recipe-card/{sku}/{lang}")
    card_url = card_url_template.format(sku=sku.upper(), lang=lang)
    out_path = out_dir / f"{sku.upper()}.pdf"

    print(f"🖨️  Génération directe pour SKU : {sku.upper()} (Anonyme)")
    print(f"    🔗 {card_url}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=CHROMIUM_PERF_ARGS)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        from .guardrails import apply_guardrails
        apply_guardrails(context)
        page = context.new_page()
        page.goto(card_url, wait_until="domcontentloaded")
        page.evaluate('''async () => {
            window.scrollTo(0, document.body.scrollHeight);
            const imgs = Array.from(document.querySelectorAll('img'));
            await Promise.all(imgs.map(img => {
                if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                return new Promise(resolve => {
                    img.onload = resolve;
                    img.onerror = resolve;
                    setTimeout(resolve, 2500);
                });
            }));
        }''')
        page.pdf(
            path=str(out_path),
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        browser.close()

    print(f"    ✅ Fiche générée : {out_path} ({out_path.stat().st_size // 1024} Ko)")
    return out_path


def run(headless: bool = True, parallel: int = 3) -> list[Path]:
    """Point d'entrée synchrone pour Phase B."""
    from playwright.async_api import async_playwright

    async def _runner():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless, args=CHROMIUM_PERF_ARGS)
            res, _ = await build_recipes_async(browser, parallel=parallel)
            await browser.close()
            return res

    return asyncio.run(_runner())
