"""Génération d'un PDF par recette (reportlab)."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Optional

import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer,
)

from .utils import DATA_DIR, RECIPES_DIR, OUTPUT_DIR, ensure_dirs, sanitize_latin1

RECIPES_PATH = DATA_DIR / "recipes.json"

ACCENT = colors.HexColor("#2E7D32")   # vert "Goodfood"
DARK = colors.HexColor("#1B1B1B")


def _styles() -> dict:
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleFr", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=DARK, spaceAfter=6 * mm,
        alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=18, textColor=ACCENT, spaceBefore=8 * mm,
        spaceAfter=3 * mm,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName="Helvetica",
        fontSize=10.5, leading=15, textColor=DARK, alignment=TA_JUSTIFY,
    )
    return {"title": title, "h2": h2, "body": body}


def _fetch_image(url: str) -> Optional[Image]:
    """Télécharge l'image d'une recette (si URL dispo)."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        img = Image(io.BytesIO(r.content))
        img.drawWidth = 160 * mm
        img.drawHeight = 90 * mm
        return img
    except Exception:  # noqa: BLE001
        return None


def build_recipe_pdf(recipe: dict, out_path: Path) -> None:
    st = _styles()
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=sanitize_latin1(recipe.get("title", "Recette")),
    )
    story = []

    story.append(Paragraph(sanitize_latin1(recipe.get("title", "Recette")), st["title"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=6 * mm))

    img = _fetch_image(recipe.get("image", ""))
    if img:
        story.append(img)
        story.append(Spacer(1, 6 * mm))

    if recipe.get("description"):
        story.append(Paragraph(sanitize_latin1(recipe["description"]), st["body"]))

    # Ingrédients
    story.append(Paragraph("Ingrédients", st["h2"]))
    ingredients = recipe.get("ingredients") or []
    if ingredients:
        for ing in ingredients:
            story.append(Paragraph(f"&bull; {sanitize_latin1(ing)}", st["body"]))
    else:
        story.append(Paragraph("(ingrédients non extraits)", st["body"]))

    # Étapes
    story.append(Paragraph("Préparation", st["h2"]))
    steps = recipe.get("steps") or []
    if steps:
        for i, step in enumerate(steps, 1):
            story.append(Paragraph(f"{i}. {sanitize_latin1(step)}", st["body"]))
            story.append(Spacer(1, 2 * mm))
    else:
        story.append(Paragraph("(étapes non extraites)", st["body"]))

    doc.build(story)


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


def run() -> Path:
    ensure_dirs()
    recipes = load_recipes()
    if not recipes:
        print("⚠️  Aucune recette à générer.")
        return RECIPES_DIR

    created = []
    for r in recipes:
        slug = r.get("matched_meal") or r.get("title") or "recette"
        fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
        out = RECIPES_DIR / f"{fname}.pdf"
        build_recipe_pdf(r, out)
        created.append(out)
        print(f"📄 {out.name}")

    print(f"\n✅ {len(created)} PDF générés dans {RECIPES_DIR}")
    return RECIPES_DIR
