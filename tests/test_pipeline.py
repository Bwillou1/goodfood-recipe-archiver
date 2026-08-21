"""Tests unitaires et d'intégration pour le pipeline Goodfood Recipe Archiver."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from pypdf import PdfReader

from src.utils import (
    chromium_launch_args, ensure_dirs, normalize, sanitize_latin1, slugify_ascii,
)
from src.ocr_receipt import extract_meal_names
from src.finder import best_match
from src import assembler, demo


class TestGoodfoodPipeline(unittest.TestCase):

    def setUp(self):
        ensure_dirs()

    def test_normalize(self):
        self.assertEqual(normalize("Poulet au Beurre !"), "poulet au beurre")
        self.assertEqual(normalize("Bœuf Bourguignon & Riz"), "boeuf bourguignon riz")
        self.assertEqual(normalize("  Saumon Teriyaki  "), "saumon teriyaki")
        self.assertEqual(normalize(""), "")

    def test_slugify_ascii(self):
        self.assertEqual(slugify_ascii("Salade façon smash burger au porc"), "Salade_facon_smash_burger_au_porc")
        self.assertEqual(slugify_ascii("Bols de fajitas à l'ail & épices"), "Bols_de_fajitas_a_lail__epices")
        self.assertEqual(slugify_ascii(""), "recette")

    def test_sanitize_latin1(self):
        raw = "🍗 Poulet à l’ail — avec « sauce » & cœur de bœuf… 20€"
        clean = sanitize_latin1(raw)
        self.assertNotIn("🍗", clean)
        self.assertIn("Poulet", clean)
        self.assertIn("l'ail", clean)
        self.assertIn("coeur de boeuf", clean)
        clean.encode("latin-1")

    def test_chromium_launch_args(self):
        # Sans variable no-sandbox
        orig_env = os.environ.get("GOODFOOD_NO_SANDBOX")
        try:
            if "GOODFOOD_NO_SANDBOX" in os.environ:
                del os.environ["GOODFOOD_NO_SANDBOX"]
            args = chromium_launch_args()
            self.assertIn("--disable-dev-shm-usage", args)

            # Avec variable no-sandbox
            os.environ["GOODFOOD_NO_SANDBOX"] = "1"
            args_sandbox = chromium_launch_args()
            self.assertIn("--no-sandbox", args_sandbox)
            self.assertIn("--disable-setuid-sandbox", args_sandbox)
        finally:
            if orig_env is not None:
                os.environ["GOODFOOD_NO_SANDBOX"] = orig_env
            elif "GOODFOOD_NO_SANDBOX" in os.environ:
                del os.environ["GOODFOOD_NO_SANDBOX"]

    def test_best_match_unified_dict(self):
        candidates = [
            {"title": "Poulet au beurre avec couscous", "card_url": "https://www2.makegoodfood.ca/recipe-card/GF105603/fr", "sku": "GF105603"},
            {"title": "Saumon teriyaki glacé à l'érable", "card_url": "https://www2.makegoodfood.ca/recipe-card/GF105597/fr", "sku": "GF105597"},
            {"title": "Tacos végé aux haricots noirs", "card_url": "https://www2.makegoodfood.ca/recipe-card/GF105500/fr", "sku": "GF105500"},
        ]
        
        match = best_match("Poulet au beurre", candidates)
        self.assertIsNotNone(match)
        cand_dict, score = match
        self.assertEqual(cand_dict["title"], "Poulet au beurre avec couscous")
        self.assertEqual(cand_dict["sku"], "GF105603")
        self.assertGreater(score, 0.7)

    def test_extract_meal_names_from_realistic_goodfood_invoice(self):
        sample_receipt = """
        MARCHÉ GOODFOOD — FACTURE #32697289
        Date de commande : 13-08-2026
        Date de livraison : 19-08-2026
        Client : Cathy Mainville
        
        Recettes (Plan: Panier Classique, 3 Recettes) - Modifiée
        Bols de crevettes gingembre-teriyaki             31,04 $
        Bols de fajitas au poulet faciles               29,50 $
        Salade façon smash burger au porc               28,00 $
        
        Autres produits
        Diced Chicken Breast, 340g/unit, Raw, FZN        0,00 $
        Tail-on Shrimp, 285g/unit, P&D, Raw, FZN         0,00 $
        Ground Pork, 340g/unit, Raw, FZN                 0,00 $
        
        Total des autres produits : 0,00 $
        Sous-total : 88,54 $
        TPS : 4,43 $
        TVQ : 8,83 $
        Total : 101,80 $
        """
        meals = extract_meal_names(sample_receipt)
        self.assertEqual(len(meals), 3)
        self.assertIn("Bols de crevettes gingembre-teriyaki", meals)
        self.assertIn("Bols de fajitas au poulet faciles", meals)
        self.assertIn("Salade façon smash burger au porc", meals)
        self.assertNotIn("Diced Chicken Breast", str(meals))
        self.assertNotIn("Tail-on Shrimp", str(meals))
        self.assertNotIn("Ground Pork", str(meals))

    def test_demo_and_assembler_end_to_end(self):
        out_pdf = demo.run()
        self.assertTrue(out_pdf.exists())
        self.assertGreater(out_pdf.stat().st_size, 1000)

        reader = PdfReader(str(out_pdf))
        self.assertGreaterEqual(len(reader.pages), 3)


if __name__ == "__main__":
    unittest.main()
