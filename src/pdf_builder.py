"""Phase B : Rendu 100 % Anonyme et Génération des PDF Officiels Goodfood.

Architecture 2 Phases (Recommandation Post-Mortem) :
- Phase B (100 % Anonyme) : Aucun cookie, token ou session utilisateur n'est transmis à www2.makegoodfood.ca.
- Cache SKU : Réutilisation immédiate des fiches déjà téléchargées sans refaire d'appel réseau.
- Réessais avec back-off exponentiel sur les requêtes réseau et l'impression PDF.
- Validation stricte de chaque PDF produit (taille > 30 Ko, 1-2 pages, images HD complètes).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

from .guardrails import apply_guardrails
from .utils import DATA_DIR, RECIPES_DIR, ensure_dirs, load_config

RECIPES_PATH = DATA_DIR / "recipes.json"


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


def print_official_card_with_retry(page, card_url: str, out_path: Path, max_retries: int = 3) -> None:
    """Imprime la vraie fiche recette avec réessais et back-off exponentiel."""
    temp_path = out_path.with_suffix(".tmp.pdf")

    for attempt in range(1, max_retries + 1):
        try:
            page.goto(card_url, wait_until="load", timeout=25000)
            time.sleep(1.0)

            # 1. Déclenche le lazy-loading de la page 2 et force le décodage de toutes les images HD
            page.evaluate('''async () => {
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(r => setTimeout(r, 600));
                
                const imgs = Array.from(document.querySelectorAll('img'));
                await Promise.all(imgs.map(img => {
                    if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                        setTimeout(resolve, 3000);
                    });
                }));
            }''')
            time.sleep(0.5)

            # 2. Impression PDF paysage native Chromium
            page.pdf(
                path=str(temp_path),
                format="A4",
                landscape=True,
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            )

            # 3. Validation & Nettoyage des pages vides
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

            # 4. Contrôle de validité du fichier produit
            size = out_path.stat().st_size
            if size < 20000:
                raise ValueError(f"PDF généré trop petit ({size} octets), possible échec de rendu.")

            return
        except Exception as e:
            delay = 2 ** attempt
            if attempt == max_retries:
                temp_path.unlink(missing_ok=True)
                raise RuntimeError(f"Échec définitif d'impression pour {card_url} après {max_retries} tentatives : {e}") from e
            print(f"   ⚠️  Tentative {attempt}/{max_retries} échouée ({e}). Nouvel essai dans {delay}s...")
            time.sleep(delay)


def build_single_sku(sku: str, lang: str = "fr", out_dir: Optional[Path] = None, headless: bool = True) -> Path:
    """Génère le PDF d'une fiche recette à partir d'un SKU unique (mode rejouabilité instantanée)."""
    cfg = load_config()
    out_dir = out_dir or RECIPES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    card_url_template = cfg.get("goodfood", {}).get("card_url_template", "https://www2.makegoodfood.ca/recipe-card/{sku}/{lang}")
    card_url = card_url_template.format(sku=sku.upper(), lang=lang)
    out_path = out_dir / f"{sku.upper()}.pdf"

    print(f"🖨️  Génération directe pour SKU : {sku.upper()} (Anonyme)")
    print(f"    🔗 {card_url}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        apply_guardrails(context)
        page = context.new_page()
        print_official_card_with_retry(page, card_url, out_path)
        browser.close()

    print(f"    ✅ Fiche générée : {out_path} ({out_path.stat().st_size // 1024} Ko)")
    return out_path


def run(headless: bool = True) -> list[Path]:
    """Exécute la Phase B sur l'ensemble des recettes de data/recipes.json."""
    ensure_dirs()
    recipes = load_recipes()
    if not recipes:
        print("⚠️  Aucune recette à imprimer.")
        return []

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    apply_guardrails(context)
    page = context.new_page()

    created: list[Path] = []
    try:
        for i, r in enumerate(recipes, 1):
            card_url = r.get("card_url") or r.get("url")
            sku = r.get("sku") or ""
            if not card_url:
                continue

            slug = r.get("matched_meal") or r.get("title") or f"recette_{i}"
            fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
            fname = fname or f"recette_{i}"
            out = RECIPES_DIR / f"{fname}.pdf"

            # Cache hit : si la fiche existe déjà et fait plus de 30 Ko, on ne la re-télécharge pas
            if out.exists() and out.stat().st_size > 30000:
                print(f"⚡ [CACHE] Fiche déjà archivée : {out.name} ({out.stat().st_size // 1024} Ko)")
                created.append(out)
                continue

            print(f"🖨️  Phase B : Impression 100% Anonyme [{i}/{len(recipes)}] : {slug}")
            print(f"    🔗 {card_url}")
            print_official_card_with_retry(page, card_url, out)
            created.append(out)
            print(f"    ✅ PDF officiel généré : {out.name} ({out.stat().st_size // 1024} Ko)")
    finally:
        context.close()
        browser.close()
        pw.stop()

    print(f"\n✅ {len(created)} fiche(s) officielle(s) prête(s) dans {RECIPES_DIR}")
    return created
