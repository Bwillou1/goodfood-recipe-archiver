"""Tests unitaires pour les garde-fous de sécurité (Strict Read-Only, Anti-Achat, Anti-Skip, Anti-Avis)."""
from __future__ import annotations

import unittest
from src.guardrails import is_url_allowed, is_mutation_allowed, is_tracker


class TestGuardrails(unittest.TestCase):

    def test_allowed_safe_urls(self):
        safe_urls = [
            "https://www.makegoodfood.ca/fr-CA/recipes",
            "https://www.makegoodfood.ca/recipes",
            "https://www.makegoodfood.ca/fr-CA/product/recipe/GF105597/saumon-teriyaki",
            "https://www2.makegoodfood.ca/recipe-card/GF105597/fr",
            "https://www2.makegoodfood.ca/recipe-card/GF105603/fr",
            "https://cdn.makegoodfood.ca/uploads/images/GF105597-0/teriyaki-salmon.webp",
        ]
        for u in safe_urls:
            self.assertTrue(is_url_allowed(u), f"URL sûre faussement bloquée : {u}")

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
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL de paiement non bloquée : {u}")

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
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL d'abonnement/skip non bloquée : {u}")

    def test_forbidden_rewards_and_credits_urls(self):
        dangerous_urls = [
            "https://www.makegoodfood.ca/rewards",
            "https://www.makegoodfood.ca/recompenses",
            "https://www.makegoodfood.ca/credits",
            "https://www.makegoodfood.ca/loyalty",
            "https://www.makegoodfood.ca/coupons",
            "https://www.makegoodfood.ca/promo",
            "https://www.makegoodfood.ca/discount",
            "https://www.makegoodfood.ca/gift-card",
            "https://www.makegoodfood.ca/referrals",
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL de récompenses/crédits non bloquée : {u}")

    def test_forbidden_reviews_and_feedback_urls(self):
        dangerous_urls = [
            "https://www.makegoodfood.ca/reviews",
            "https://www.makegoodfood.ca/avis",
            "https://www.makegoodfood.ca/feedback",
            "https://www.makegoodfood.ca/rating",
            "https://www.makegoodfood.ca/survey",
            "https://www.makegoodfood.ca/comments",
        ]
        for u in dangerous_urls:
            self.assertFalse(is_url_allowed(u), f"URL d'avis/feedback non bloquée : {u}")

    def test_http_mutation_blocking(self):
        # GET est permis partout
        self.assertTrue(is_mutation_allowed("GET", "https://www.makegoodfood.ca/fr-CA/recipes"))
        
        # POST est permis UNIQUEMENT pour le login Firebase/Goodfood
        self.assertTrue(is_mutation_allowed("POST", "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"))
        self.assertTrue(is_mutation_allowed("POST", "https://www.makegoodfood.ca/login"))
        
        # POST/PUT/DELETE/PATCH sont bloqués partout ailleurs
        self.assertFalse(is_mutation_allowed("POST", "https://www.makegoodfood.ca/api/order/123"))
        self.assertFalse(is_mutation_allowed("PUT", "https://www.makegoodfood.ca/api/user/profile"))
        self.assertFalse(is_mutation_allowed("DELETE", "https://www.makegoodfood.ca/api/subscription"))
        self.assertFalse(is_mutation_allowed("PATCH", "https://www.makegoodfood.ca/api/cart"))

    def test_session_trackers_blocked(self):
        trackers = [
            "https://static.hotjar.com/c/hotjar-12345.js",
            "https://browser-intake-datadoghq.com/api/v2/rum",
            "https://api.segment.io/v1/t",
            "https://www.google-analytics.com/analytics.js",
            "https://googletagmanager.com/gtm.js",
            "https://edge.fullstory.com/s/fs.js",
            "https://bat.bing.com/bat.js",
            "https://analytics.tiktok.com/i18n/pixel/events.js",
        ]
        for t in trackers:
            self.assertTrue(is_tracker(t), f"Traceur non détecté : {t}")


if __name__ == "__main__":
    unittest.main()
