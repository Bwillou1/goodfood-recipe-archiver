"""Tests unitaires pour les garde-fous de sécurité (Strict Read-Only)."""
from __future__ import annotations

import unittest
from src.guardrails import is_url_allowed


class TestGuardrails(unittest.TestCase):

    def test_allowed_urls(self):
        safe_urls = [
            "https://www.makegoodfood.ca/fr-CA/recipes",
            "https://www.makegoodfood.ca/recipes",
            "https://www.makegoodfood.ca/fr-CA/product/recipe/GF105597/saumon-teriyaki",
            "https://www.makegoodfood.ca/fr-CA/product/recipe/GF105652/bols-de-crevettes?deliveryDate=2026-09-13",
            "https://cdn.makegoodfood.ca/uploads/images/GF105597-0/teriyaki-glazed-salmon.webp",
        ]
        for u in safe_urls:
            self.assertTrue(is_url_allowed(u), f"URL sûre faussement bloquée : {u}")

    def test_forbidden_sensitive_urls(self):
        dangerous_urls = [
            "https://www.makegoodfood.ca/checkout",
            "https://www.makegoodfood.ca/fr-CA/checkout",
            "https://www.makegoodfood.ca/cart",
            "https://www.makegoodfood.ca/panier",
            "https://www.makegoodfood.ca/account/payment",
            "https://www.makegoodfood.ca/account/billing",
            "https://www.makegoodfood.ca/credit-card",
            "https://www.makegoodfood.ca/wallet",
            "https://www.makegoodfood.ca/portefeuille",
            "https://www.makegoodfood.ca/subscriptions/modify",
            "https://www.makegoodfood.ca/subscriptions/cancel",
            "https://www.makegoodfood.ca/orders/cancel",
            "https://www.makegoodfood.ca/orders/edit",
            "https://www.makegoodfood.ca/api/v1/checkout",
            "https://www.makegoodfood.ca/api/v1/payment",
            "https://www.makegoodfood.ca/api/cart/add",
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL dangereuse non bloquée : {u}")


if __name__ == "__main__":
    unittest.main()
