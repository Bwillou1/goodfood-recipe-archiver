"""Démo : génère des PDF d'exemple à partir de données fictives.

Permet de valider le rendu (PDF par recette + PDF final) sans compte Goodfood,
et sans réseau.
"""
from __future__ import annotations

from pathlib import Path

from . import assembler, pdf_builder
from .utils import RECIPES_DIR, ensure_dirs

SAMPLE_RECIPES = [
    {
        "title": "Poulet au beurre à l'indienne",
        "matched_meal": "Poulet au beurre",
        "description": "Un classique crémeux et parfumé, prêt en 30 minutes.",
        "image": "",
        "ingredients": [
            "2 poitrines de poulet",
            "1 oignon haché",
            "2 c. à soupe de pâte de tomate",
            "200 ml de crème 15%",
            "1 c. à thé de garam masala",
            "Riz basmati, en accompagnement",
        ],
        "steps": [
            "Faire revenir l'oignon dans un peu d'huile jusqu'à ce qu'il soit tendre.",
            "Ajouter le poulet et le faire dorer de tous les côtés.",
            "Incorporer la pâte de tomate et le garam masala, cuire 1 minute.",
            "Verser la crème, mijoter 10 minutes à feu doux.",
            "Servir sur le riz basmati et garnir de coriandre.",
        ],
    },
    {
        "title": "Saumon teriyaki et légumes rôtis",
        "matched_meal": "Saumon teriyaki",
        "description": "Saumon glacé au teriyaki, brocoli et carottes rôtis.",
        "image": "",
        "ingredients": [
            "2 filets de saumon",
            "3 c. à soupe de sauce teriyaki",
            "1 brocoli",
            "2 carottes",
            "Graines de sésame",
        ],
        "steps": [
            "Préchauffer le four à 220 °C (425 °F).",
            "Rôtir les légumes 15 minutes avec un filet d'huile.",
            "Badigeonner le saumon de teriyaki et l'ajouter sur la plaque.",
            "Cuire 10 minutes de plus, jusqu'à cuisson désirée.",
            "Parsemer de graines de sésame et servir.",
        ],
    },
]


def run_demo() -> Path:
    ensure_dirs()
    print("🎬 Génération des PDF d'exemple...\n")
    for r in SAMPLE_RECIPES:
        out = RECIPES_DIR / f"demo_{r['matched_meal'].replace(' ', '_')}.pdf"
        pdf_builder.build_recipe_pdf(r, out)
        print(f"📄 {out.name}")

    final = assembler.run()
    print(f"\n✅ Démo terminée → {final}")
    return final


# Alias pour cohérence avec les autres modules
run = run_demo
