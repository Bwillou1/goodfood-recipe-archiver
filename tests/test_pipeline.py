"""Tests unitaires et d'intégration pour le pipeline Goodfood Recipe Archiver."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from pypdf import PdfReader

from src.utils import normalize, sanitize_latin1, DATA_DIR, RECIPES_DIR, OUTPUT_DIR, ensure_dirs
from src.ocr_receipt import extract_meal_names
from src.finder import best_match
from src.pdf_builder import build_recipe_pdf
from src import assembler, demo


class TestGoodfoodPipeline(unittest.TestCase):

    def setUp(self):
        ensure_dirs()

    def test_normalize(self):
        self.assertEqual(normalize("Poulet au Beurre !"), "poulet au beurre")
        self.assertEqual(normalize("Bœuf Bourguignon & Riz"), "boeuf bourguignon riz")
        self.assertEqual(normalize("  Saumon Teriyaki  "), "saumon teriyaki")
        self.assertEqual(normalize(""), "")

    def test_sanitize_latin1(self):
        raw = "🍗 Poulet à l’ail — avec « sauce » & cœur de bœuf… 20€"
        clean = sanitize_latin1(raw)
        self.assertNotIn("🍗", clean)
        self.assertIn("Poulet", clean)
        self.assertIn("l'ail", clean)
        self.assertIn("coeur de boeuf", clean)
        # Vérifie que l'encodage latin-1 ne crash pas
        clean.encode("latin-1")

    def test_best_match(self):
        candidates = [
            ("Poulet au beurre avec riz basmati", "https://makegoodfood.ca/recette/poulet-beurre"),
            ("Saumon teriyaki glacé à l'érable", "https://makegoodfood.ca/recette/saumon-teriyaki"),
            ("Tacos végé aux haricots noirs", "https://makegoodfood.ca/recette/tacos-vege"),
        ]
        
        # Test match exact partiel
        match = best_match("Poulet au beurre", candidates)
        self.assertIsNotNone(match)
        self.assertEqual(match[0], "Poulet au beurre avec riz basmati")
        self.assertGreater(match[2], 0.7)

        # Test match avec légère faute
        match2 = best_match("Saumon teriyaky", candidates)
        self.assertIsNotNone(match2)
        self.assertEqual(match2[0], "Saumon teriyaki glacé à l'érable")
        self.assertGreater(match2[2], 0.7)

    def test_extract_meal_names_from_receipt_text(self):
        sample_receipt = """
        GOODFOOD FACTURE #123456
        Date: 2026-08-15
        Client: Jean Tremblay
        Livraison: 0.00$
        
        Poulet au beurre crémeux
        Qty: 1   19.99$
        
        Saumon teriyaki à l'érable
        Qty: 1   24.99$
        
        Sous-total: 44.98$
        TPS (5%): 2.25$
        TVQ (9.975%): 4.49$
        Total: 51.72$
        Merci d'avoir choisi Goodfood !
        """
        meals = extract_meal_names(sample_receipt)
        self.assertIn("Poulet au beurre crémeux", meals)
        self.assertIn("Saumon teriyaki à l'érable", meals)
        self.assertNotIn("GOODFOOD FACTURE #123456", meals)
        self.assertNotIn("Sous-total: 44.98$", meals)
        self.assertNotIn("Total: 51.72$", meals)

    def test_pdf_generation_and_assembly(self):
        test_recipe = {
            "title": "Bavette de bœuf au poivre",
            "matched_meal": "Bavette de bœuf",
            "image": "",
            "description": "Un classique bistro rapide et savoureux.",
            "ingredients": ["2 bavettes de bœuf", "1 échalote française", "Poivre noir concassé", "Crème 35%"],
            "steps": ["Saisir la viande 3 minutes par côté.", "Préparer la sauce au poivre.", "Servir chaud."],
        }
        
        pdf_file = RECIPES_DIR / "test_bavette.pdf"
        build_recipe_pdf(test_recipe, pdf_file)
        self.assertTrue(pdf_file.exists())
        self.assertGreater(pdf_file.stat().st_size, 500)

        # Vérifie lecture avec pypdf
        reader = PdfReader(str(pdf_file))
        self.assertGreaterEqual(len(reader.pages), 1)

    def test_demo_and_assembler_end_to_end(self):
        out_pdf = demo.run()
        self.assertTrue(out_pdf.exists())
        self.assertGreater(out_pdf.stat().st_size, 1000)

        # Vérifie que le PDF final contient la page de garde + les recettes
        reader = PdfReader(str(out_pdf))
        self.assertGreaterEqual(len(reader.pages), 3)  # 1 page de garde + 2 recettes


if __name__ == "__main__":
    unittest.main()
