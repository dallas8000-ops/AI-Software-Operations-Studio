import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from django.test import Client, TestCase, override_settings

from django.contrib.auth import get_user_model

from apps.billing.models import Subscription
from apps.billing.webhooks import _sync_subscription


@override_settings(
    SAAS_STRIPE_WEBHOOK_SECRET="whsec_test_secret",
    SAAS_STRIPE_SECRET_KEY="sk_test_fake",
)
class BillingWebhookDeliveryTests(TestCase):
    def _sign(self, payload: str) -> dict[str, str]:
        ts = str(int(time.time()))
        sig = hmac.new(
            b"whsec_test_secret",
            f"{ts}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "HTTP_STRIPE_SIGNATURE": f"t={ts},v1={sig}",
        }

    def test_post_not_csrf_blocked(self):
        client = Client()
        response = client.post("/api/v1/billing/webhook/", data="{}", content_type="application/json")
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(response.status_code, 400)

    def test_unhandled_event_returns_200(self):
        payload = json.dumps(
            {
                "id": "evt_test_unhandled",
                "object": "event",
                "type": "customer.updated",
                "data": {"object": {"id": "cus_x", "object": "customer"}},
            }
        )
        client = Client()
        response = client.post(
            "/api/v1/billing/webhook/",
            data=payload,
            content_type="application/json",
            **self._sign(payload),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(b"received", response.content)

    def test_subscription_update_reads_item_period_end_and_cancellation(self):
        user = get_user_model().objects.create_user(
            email="cancel-state@example.com",
            password="test-pass-123",
        )
        period_end = 1785643200

        _sync_subscription(
            str(user.pk),
            {
                "id": "sub_cancel_test",
                "customer": "cus_cancel_test",
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
            },
        )

        subscription = Subscription.objects.get(user=user)
        self.assertTrue(subscription.cancel_at_period_end)
        self.assertEqual(subscription.current_period_end, datetime.fromtimestamp(period_end, tz=timezone.utc))
