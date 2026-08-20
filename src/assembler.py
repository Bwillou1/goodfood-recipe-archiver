"""Assemblage de toutes les fiches officielles Goodfood en un livre de recettes PDF unique."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .utils import OUTPUT_DIR, RECIPES_DIR, ensure_dirs, sanitize_latin1

FINAL_PATH = OUTPUT_DIR / "Goodfood_recettes.pdf"


def _cover_page(pdf_path: Path, recipes_count: int, titles: list[str]) -> None:
    """Génère une page de garde élégante en format Paysage (Landscape A4)."""
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "CoverTitle", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=26, leading=30, textColor=colors.HexColor("#00838D"),  # Teal Goodfood
        alignment=TA_CENTER, spaceAfter=4 * mm,
    )
    sub = ParagraphStyle(
        "CoverSub", parent=base["Normal"], fontSize=13, leading=17,
        textColor=colors.HexColor("#444444"), alignment=TA_CENTER,
    )

    doc = SimpleDocTemplate(str(pdf_path), pagesize=landscape(A4),
                            leftMargin=30 * mm, rightMargin=30 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    story = [
        Spacer(1, 15 * mm),
        Paragraph("Mes Fiches Recettes Marché Goodfood", title),
        HRFlowable(width="60%", thickness=1.5, color=colors.HexColor("#00838D"),
                   spaceAfter=8 * mm),
        Paragraph(f"{recipes_count} fiches officielles archivées", sub),
        Spacer(1, 10 * mm),
    ]
    table_data = [["#", "Recette Officielle"]]
    for i, t in enumerate(titles, 1):
        table_data.append([str(i), sanitize_latin1(t)])
    tbl = Table(table_data, colWidths=[20 * mm, 180 * mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00838D")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F7F7")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B2DFDB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    doc.build(story)


def run(pdf_paths: Optional[list[Path]] = None) -> Path:
    ensure_dirs()
    if pdf_paths is not None:
        pdfs = [p for p in pdf_paths if p.exists()]
    else:
        pdfs = sorted([p for p in RECIPES_DIR.glob("*.pdf") if not p.name.startswith("demo_") and not p.name.startswith("test_") and not p.name.startswith("official_card_") and not p.name.startswith("GF")])
        if not pdfs:
            pdfs = sorted(RECIPES_DIR.glob("*.pdf"))

    if not pdfs:
        print("⚠️  Aucune fiche recette trouvée. Lance d'abord : python -m src.cli build")
        return FINAL_PATH

    titles = [p.stem.replace("_", " ") for p in pdfs]

    cover = OUTPUT_DIR / "_cover.pdf"
    _cover_page(cover, len(pdfs), titles)

    writer = PdfWriter()
    for p in [cover, *pdfs]:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)

    with open(FINAL_PATH, "wb") as f:
        writer.write(f)

    cover.unlink(missing_ok=True)
    print(f"📚 PDF final : {FINAL_PATH} ({len(pdfs)} fiches officielles, {len(writer.pages)} pages)")
    return FINAL_PATH
