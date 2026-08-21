"""Tests unitaires pour les garde-fous de sécurité (Strict Read-Only, Anti-Achat, Anti-Skip, Anti-Traceurs)."""
from __future__ import annotations

import unittest
from src.guardrails import is_url_allowed, is_mutation_allowed, is_tracker, _check_route


class TestGuardrails(unittest.TestCase):

    def test_allowed_safe_urls(self):
        safe_urls = [
            "https://www.makegoodfood.ca/fr-CA/recipes",
            "https://www.makegoodfood.ca/recipes",
            "https://www.makegoodfood.ca/fr-CA/recipe-cards",
            "https://www.makegoodfood.ca/fr-CA/product/recipe/GF105597/saumon-teriyaki",
            "https://www2.makegoodfood.ca/recipe-card/GF105597/fr",
            "https://www2.makegoodfood.ca/recipe-card/GF105603/fr",
            "https://cdn.makegoodfood.ca/uploads/images/GF105597-0/teriyaki-salmon.webp",
        ]
        for u in safe_urls:
            self.assertTrue(is_url_allowed(u), f"URL sûre faussement bloquée : {u}")

    def test_benign_get_endpoints_allowed(self):
        """Vérifie que les endpoints de lecture bénins (ratings, promotion) sont autorisés en GET."""
        benign_urls = [
            "https://api.makegoodfood.ca/v2/ratings?userId=8a7e596a-aa30-4164-a4b1-533605f687ef&locale=fr",
            "https://api.makegoodfood.ca/user/8a7e596a-aa30-4164-a4b1-533605f687ef/promotion",
            "https://www.makegoodfood.ca/promotion",
        ]
        for u in benign_urls:
            self.assertTrue(is_url_allowed(u, method="GET"), f"GET bénin non autorisé : {u}")
            allowed, should_log, reason = _check_route(u, "GET", "xhr")
            self.assertTrue(allowed, f"Route non permise : {u}")
            self.assertFalse(should_log, "Ne doit pas logger en alerte")

    def test_forbidden_cart_and_payment_urls(self):
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
            "https://api.makegoodfood.ca/cart/62271042",
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL de paiement/panier non bloquée : {u}")

    def test_forbidden_subscription_and_skip_urls(self):
        dangerous_urls = [
            "https://www.makegoodfood.ca/subscription",
            "https://www.makegoodfood.ca/abonnement",
            "https://www.makegoodfood.ca/skip",
            "https://www.makegoodfood.ca/unskip",
            "https://www.makegoodfood.ca/pause",
            "https://www.makegoodfood.ca/resume",
            "https://www.makegoodfood.ca/delivery-schedule",
            "https://www.makegoodfood.ca/my-plan",
            "https://www.makegoodfood.ca/subscriptions/modify",
            "https://www.makegoodfood.ca/subscriptions/cancel",
            "https://www.makegoodfood.ca/orders/cancel",
            "https://api.makegoodfood.ca/user/8a7e596a-aa30-4164-a4b1-533605f687ef/subscription/last-cancelled",
            "https://api.makegoodfood.ca/subscription/92378930-37eb-4811-a57e-25654b0316b9",
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL d'abonnement/skip non bloquée : {u}")

    def test_http_mutation_blocking(self):
        self.assertTrue(is_mutation_allowed("GET", "https://www.makegoodfood.ca/fr-CA/recipes"))
        self.assertTrue(is_mutation_allowed("POST", "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"))
        self.assertTrue(is_mutation_allowed("POST", "https://www.makegoodfood.ca/login"))
        
        # Mutations HTTP bloquées
        self.assertFalse(is_mutation_allowed("POST", "https://www.makegoodfood.ca/api/order/123"))
        self.assertFalse(is_mutation_allowed("PUT", "https://www.makegoodfood.ca/api/user/profile"))
        self.assertFalse(is_mutation_allowed("DELETE", "https://www.makegoodfood.ca/api/subscription"))
        self.assertFalse(is_mutation_allowed("PATCH", "https://www.makegoodfood.ca/api/cart"))
        self.assertFalse(is_mutation_allowed("POST", "https://api.makegoodfood.ca/v2/ratings"))

    def test_session_trackers_and_rum_blocked_silently(self):
        trackers = [
            "https://static.hotjar.com/c/hotjar-12345.js",
            "https://browser-intake-datadoghq.com/api/v2/rum",
            "https://api.segment.io/v1/t",
            "https://www.google-analytics.com/analytics.js",
            "https://googletagmanager.com/gtm.js",
            "https://edge.fullstory.com/s/fs.js",
            "https://bat.bing.com/bat.js",
            "https://analytics.tiktok.com/i18n/pixel/events.js",
            "https://www.makegoodfood.ca/cdn-cgi/rum?",
        ]
        for t in trackers:
            self.assertTrue(is_tracker(t), f"Traceur non détecté : {t}")
            allowed, should_log, reason = _check_route(t, "GET", "xhr")
            self.assertFalse(allowed, f"Traceur non bloqué : {t}")
            self.assertFalse(should_log, f"Traceur ne doit pas générer d'alerte bruyante : {t}")


if __name__ == "__main__":
    unittest.main()
