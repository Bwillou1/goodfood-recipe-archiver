"""Démo : génère des PDF d'exemple à partir de données fictives.

Permet de valider l'assemblage et le pipeline sans compte Goodfood.
"""
from __future__ import annotations

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from . import assembler
from .utils import RECIPES_DIR, ensure_dirs


def run_demo() -> Path:
    ensure_dirs()
    print("🎬 Génération des PDF d'exemple...\n")
    styles = getSampleStyleSheet()

    demo_recipes = ["Poulet au beurre", "Saumon teriyaki"]
    created = []
    for name in demo_recipes:
        out = RECIPES_DIR / f"demo_{name.replace(' ', '_')}.pdf"
        doc = SimpleDocTemplate(str(out), pagesize=A4)
        doc.build([Paragraph(f"Recette Démo : {name}", styles["Title"]), Spacer(1, 20)])
        created.append(out)
        print(f"📄 {out.name}")

    final = assembler.run(pdf_paths=created)
    print(f"\n✅ Démo terminée → {final}")
    return final


run = run_demo
