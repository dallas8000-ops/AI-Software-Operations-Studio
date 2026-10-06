"""Studio pricing regression tests: checkout offers exactly Team $149/mo and Agency $399/mo."""

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase


class PlansPricingTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(email="plans@example.com", password="test-pass-123")
        self.client.force_authenticate(user)

    @override_settings(
        SAAS_STRIPE_SECRET_KEY="rk_test_billing",
        SAAS_STRIPE_PRICE_TEAM="price_team",
        SAAS_STRIPE_PRICE_AGENCY="price_agency",
    )
    def test_offers_team_and_agency_at_current_prices(self):
        plans = self.client.get("/api/v1/billing/plans/").data["plans"]
        self.assertEqual(
            [(p["tier"], p["priceId"], p["amount"], p["currency"]) for p in plans],
            [("Team", "price_team", 14900, "usd"), ("Agency", "price_agency", 39900, "usd")],
        )

    @override_settings(
        SAAS_STRIPE_SECRET_KEY="rk_test_billing",
        SAAS_STRIPE_PRICE_TEAM="",
        SAAS_STRIPE_PRICE_AGENCY="",
        SAAS_STRIPE_PRICE_STARTER="price_old_starter",
        SAAS_STRIPE_PRICE_PRO="price_old_pro",
        SAAS_STRIPE_PRICE_ENTERPRISE="price_old_enterprise",
    )
    def test_retired_starter_pro_enterprise_prices_are_not_sold(self):
        self.assertEqual(self.client.get("/api/v1/billing/plans/").data["plans"], [])
        response = self.client.post(
            "/api/v1/billing/checkout/",
            {"priceId": "price_old_starter", "domain": "app.example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
