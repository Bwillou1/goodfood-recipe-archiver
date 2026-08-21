"""Assemblage des fiches officielles Goodfood en un livre PDF complet et élégant.

Améliorations P1 / P3 :
- Page de garde paysagée avec métadonnées de facture (Client, N° de commande, Date de livraison).
- Insertion de métadonnées PDF standard (Titre, Auteur, Sujet).
- Support du chemin de sortie personnalisable (--out).
"""
from __future__ import annotations

import json
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

from .utils import DATA_DIR, OUTPUT_DIR, RECIPES_DIR, ensure_dirs, sanitize_latin1

FINAL_PATH = OUTPUT_DIR / "Goodfood_recettes.pdf"
MEALS_PATH = DATA_DIR / "meals.json"


def _cover_page(
    pdf_path: Path,
    recipes_count: int,
    titles: list[str],
    meta: Optional[dict] = None,
) -> None:
    """Génère une page de garde élégante en format Paysage (Landscape A4)."""
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CoverTitle", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=24, leading=28, textColor=colors.HexColor("#00838D"),
        alignment=TA_CENTER, spaceAfter=3 * mm,
    )
    sub_style = ParagraphStyle(
        "CoverSub", parent=base["Normal"], fontSize=12, leading=16,
        textColor=colors.HexColor("#444444"), alignment=TA_CENTER,
    )
    meta_style = ParagraphStyle(
        "CoverMeta", parent=base["Normal"], fontSize=10, leading=14,
        textColor=colors.HexColor("#666666"), alignment=TA_CENTER,
    )

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=landscape(A4),
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    meta_lines = []
    if meta:
        cust = meta.get("customer")
        order = meta.get("order_number")
        deliv = meta.get("delivery_date")
        if cust:
            meta_lines.append(f"Client : {sanitize_latin1(cust)}")
        if order:
            meta_lines.append(f"Commande #{order}")
        if deliv:
            meta_lines.append(f"Livraison : {deliv}")

    story = [
        Spacer(1, 10 * mm),
        Paragraph("Mes Fiches Recettes Marché Goodfood", title_style),
        HRFlowable(width="60%", thickness=1.5, color=colors.HexColor("#00838D"), spaceAfter=6 * mm),
        Paragraph(f"{recipes_count} fiches officielles archivées", sub_style),
    ]

    if meta_lines:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(" • ".join(meta_lines), meta_style))

    story.append(Spacer(1, 8 * mm))

    table_data = [["#", "Recette Officielle"]]
    for i, t in enumerate(titles, 1):
        table_data.append([str(i), sanitize_latin1(t)])

    tbl = Table(table_data, colWidths=[20 * mm, 190 * mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00838D")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F7F7")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B2DFDB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    doc.build(story)


def run(pdf_paths: Optional[list[Path]] = None, out_path: Optional[Path] = None) -> Path:
    ensure_dirs()
    target_out = out_path or FINAL_PATH
    target_out.parent.mkdir(parents=True, exist_ok=True)

    if pdf_paths is not None:
        pdfs = [p for p in pdf_paths if p.exists()]
    else:
        # Exclusion stricte des démos, tests et fichiers temporaires
        pdfs = sorted([
            p for p in RECIPES_DIR.glob("*.pdf")
            if not p.name.startswith(("demo_", "test_", "_", "official_card_"))
        ])

    if not pdfs:
        print("⚠️  Aucune fiche recette trouvée pour l'assemblage.")
        return target_out

    meta = {}
    if MEALS_PATH.exists():
        try:
            meta = json.loads(MEALS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    titles = [p.stem.replace("_", " ") for p in pdfs]

    cover = target_out.parent / "_cover.tmp.pdf"
    _cover_page(cover, len(pdfs), titles, meta=meta)

    writer = PdfWriter()
    for p in [cover, *pdfs]:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)

    # Métadonnées PDF
    writer.add_metadata({
        "/Title": "Mes Fiches Recettes Marché Goodfood",
        "/Author": "Marché Goodfood",
        "/Subject": f"Commande #{meta.get('order_number', '')}" if meta.get("order_number") else "Livre de recettes",
        "/Creator": "Goodfood Recipe Archiver",
    })

    with open(target_out, "wb") as f:
        writer.write(f)

    cover.unlink(missing_ok=True)
    print(f"📚 PDF final : {target_out} ({len(pdfs)} fiches officielles, {len(writer.pages)} pages)")
    return target_out
