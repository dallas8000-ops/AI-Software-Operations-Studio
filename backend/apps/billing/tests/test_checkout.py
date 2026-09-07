from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.billing.models import Subscription
from apps.billing.views import _stripe_object_payload


@override_settings(
    SAAS_STRIPE_SECRET_KEY="rk_test_billing",
    SAAS_STRIPE_PRICE_STARTER="price_starter",
    SAAS_STRIPE_PRICE_PRO="price_pro",
    SAAS_STRIPE_PRICE_ENTERPRISE="price_enterprise",
    SAAS_BILLING_RETURN_URL="https://app.example.com",
)
class CheckoutTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="checkout@example.com",
            password="test-pass-123",
        )
        self.client.force_authenticate(self.user)

    def test_stripe_object_payload_uses_public_sdk_conversion(self):
        class StripeResource:
            def to_dict(self):
                return {"id": "sub_recursive", "items": {"data": []}}

        self.assertEqual(
            _stripe_object_payload(StripeResource()),
            {"id": "sub_recursive", "items": {"data": []}},
        )

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_rejects_unconfigured_price(self, create_session):
        response = self.client.post(
            "/api/v1/billing/checkout/",
            {"priceId": "price_not_ours", "domain": "app.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Unknown or unavailable plan")
        create_session.assert_not_called()

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_rejects_non_string_checkout_fields(self, create_session):
        response = self.client.post(
            "/api/v1/billing/checkout/",
            {"priceId": ["price_pro"], "domain": {"host": "app.example.com"}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        create_session.assert_not_called()

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_configured_price_creates_dynamic_payment_checkout(self, create_session):
        create_session.return_value = SimpleNamespace(url="https://checkout.stripe.com/test")

        response = self.client.post(
            "/api/v1/billing/checkout/",
            {"priceId": "price_pro", "domain": "app.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        params = create_session.call_args.kwargs
        self.assertEqual(params["mode"], "subscription")
        self.assertEqual(params["line_items"], [{"price": "price_pro", "quantity": 1}])
        self.assertNotIn("payment_method_types", params)

    @patch("apps.billing.views.stripe.billing_portal.Session.create")
    def test_portal_uses_current_stripe_sdk_namespace(self, create_session):
        Subscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_portal_test",
            status=Subscription.Status.ACTIVE,
        )
        create_session.return_value = SimpleNamespace(url="https://billing.stripe.com/test")

        response = self.client.post("/api/v1/billing/portal/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://billing.stripe.com/test")
        create_session.assert_called_once_with(
            customer="cus_portal_test",
            return_url="https://app.example.com/billing",
        )

    @override_settings(SAAS_STRIPE_SECRET_KEY="")
    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_checkout_returns_503_when_secret_missing(self, create_session):
        # When the platform secret is not configured, the endpoint should return 503
        response = self.client.post(
            "/api/v1/billing/checkout/",
            {"priceId": "price_pro", "domain": "app.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        create_session.assert_not_called()

    @patch("apps.billing.views.stripe.billing_portal.Session.create")
    def test_portal_ignores_client_supplied_customerid(self, create_session):
        # Ensure a malicious client-supplied customerId cannot override stored customer
        Subscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_portal_owner",
            status=Subscription.Status.ACTIVE,
        )
        create_session.return_value = SimpleNamespace(url="https://billing.stripe.com/test")

        response = self.client.post(
            "/api/v1/billing/portal/",
            {"customerId": "cus_malicious"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://billing.stripe.com/test")
        # Must call with the stored customer id, not the client-supplied value
        create_session.assert_called_once_with(
            customer="cus_portal_owner",
            return_url="https://app.example.com/billing",
        )

    @patch("apps.billing.views.stripe.Subscription.retrieve")
    def test_subscription_read_reconciles_cancellation_from_stripe(self, retrieve):
        period_end = 1785643200
        Subscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_reconcile_test",
            stripe_subscription_id="sub_reconcile_test",
            status=Subscription.Status.ACTIVE,
        )
        retrieve.return_value = {
            "id": "sub_reconcile_test",
            "customer": "cus_reconcile_test",
            "status": "active",
            "cancel_at_period_end": True,
            "items": {
                "data": [
                    {
                        "current_period_end": period_end,
                        "price": {"id": "price_starter", "metadata": {"tier": "Starter"}},
                    }
                ]
            },
        }

        response = self.client.get("/api/v1/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["cancelAtPeriodEnd"])
        self.assertIsNotNone(response.data["currentPeriodEnd"])
        retrieve.assert_called_once_with("sub_reconcile_test")
