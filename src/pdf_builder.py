"""Génération ultra-rapide et élégante d'un PDF par recette (reportlab)."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Optional

import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from .utils import DATA_DIR, RECIPES_DIR, ensure_dirs, sanitize_latin1

RECIPES_PATH = DATA_DIR / "recipes.json"

ACCENT = colors.HexColor("#2E7D32")   # vert "Goodfood"
DARK = colors.HexColor("#1B1B1B")
LIGHT_BG = colors.HexColor("#F4F8F4")
BORDER_COLOR = colors.HexColor("#E0E0E0")

# Session HTTP réutilisable pour accélérer les téléchargements d'images
_HTTP_SESSION: Optional[requests.Session] = None


def get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        _HTTP_SESSION = requests.Session()
        _HTTP_SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        })
    return _HTTP_SESSION


def _styles() -> dict:
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleFr", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=DARK, spaceAfter=4 * mm,
        alignment=TA_CENTER,
    )
    badge = ParagraphStyle(
        "Badge", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=11, textColor=ACCENT, alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=ACCENT, spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName="Helvetica",
        fontSize=9.5, leading=13.5, textColor=DARK, alignment=TA_JUSTIFY,
    )
    step_item = ParagraphStyle(
        "StepItem", parent=base["BodyText"], fontName="Helvetica",
        fontSize=9.5, leading=13.5, textColor=DARK, alignment=TA_LEFT,
    )
    return {"title": title, "badge": badge, "h2": h2, "body": body, "step_item": step_item}


def _fetch_image(url: str) -> Optional[Image]:
    """Télécharge l'image d'une recette rapidement (avec session réutilisable)."""
    if not url:
        return None
    try:
        session = get_http_session()
        r = session.get(url, timeout=5)
        r.raise_for_status()
        img = Image(io.BytesIO(r.content))
        img.drawWidth = 155 * mm
        img.drawHeight = 85 * mm
        return img
    except Exception:
        return None


def build_recipe_pdf(recipe: dict, out_path: Path) -> None:
    st = _styles()
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=sanitize_latin1(recipe.get("title", "Recette")),
    )
    story = []

    # Titre
    clean_title = sanitize_latin1(recipe.get("title", "Recette"))
    story.append(Paragraph(clean_title, st["title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4 * mm))

    # Image
    img = _fetch_image(recipe.get("image", ""))
    if img:
        story.append(img)
        story.append(Spacer(1, 4 * mm))

    # Description
    if recipe.get("description"):
        story.append(Paragraph(sanitize_latin1(recipe["description"]), st["body"]))
        story.append(Spacer(1, 3 * mm))

    # Ingrédients
    story.append(Paragraph("Ingrédients", st["h2"]))
    ingredients = recipe.get("ingredients") or []
    if ingredients:
        # Affichage structuré en 2 colonnes si la liste est longue
        for ing in ingredients:
            story.append(Paragraph(f"&bull; {sanitize_latin1(ing)}", st["body"]))
    else:
        story.append(Paragraph("(ingrédients non extraits)", st["body"]))

    story.append(Spacer(1, 3 * mm))

    # Préparation
    story.append(Paragraph("Préparation", st["h2"]))
    steps = recipe.get("steps") or []
    if steps:
        for i, step in enumerate(steps, 1):
            clean_step = sanitize_latin1(step)
            # Évite la répétition '1. Étape 1:' si déjà dans le texte
            if clean_step.lower().startswith(f"étape {i}:") or clean_step.lower().startswith(f"step {i}:"):
                story.append(Paragraph(f"<b>{clean_step[:10]}</b> {clean_step[10:]}", st["step_item"]))
            else:
                story.append(Paragraph(f"<b>Étape {i}:</b> {clean_step}", st["step_item"]))
            story.append(Spacer(1, 1.5 * mm))
    else:
        story.append(Paragraph("(étapes non extraites)", st["body"]))

    doc.build(story)


def load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        raise FileNotFoundError(f"{RECIPES_PATH} introuvable. Lance d'abord : python -m src.cli find")
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"]


def run() -> list[Path]:
    ensure_dirs()
    recipes = load_recipes()
    if not recipes:
        print("⚠️  Aucune recette à générer.")
        return []

    created: list[Path] = []
    for i, r in enumerate(recipes, 1):
        slug = r.get("matched_meal") or r.get("title") or f"recette_{i}"
        fname = "".join(c for c in slug if c.isalnum() or c in " -_").strip().replace(" ", "_")[:60]
        fname = fname or f"recette_{i}"
        out = RECIPES_DIR / f"{fname}.pdf"
        build_recipe_pdf(r, out)
        created.append(out)
        print(f"📄 {out.name}")

    print(f"\n✅ {len(created)} PDF générés dans {RECIPES_DIR}")
    return created
