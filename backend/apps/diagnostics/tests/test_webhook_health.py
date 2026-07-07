from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.diagnostics.webhook_health import webhook_health
from apps.projects.models import Project


class WebhookHealthDeliveryEvidenceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="webhooks@example.com",
            password="test-pass-123",
        )
        self.project = Project.objects.create(
            owner=self.user,
            slug="webhook-app",
            name="Webhook App",
            local_path="C:\\webhook-app",
        )

    @patch("apps.diagnostics.webhook_health.assess_webhook_delivery")
    @patch("apps.diagnostics.webhook_health.resolve_expected_webhook_url")
    @patch("apps.diagnostics.webhook_health.get_secret", return_value="sk_test_secret")
    @patch("apps.diagnostics.webhook_health.stripe")
    def test_no_recent_events_are_inactive_not_failed(
        self, stripe_client, _get_secret, expected_url, assess_delivery
    ):
        from apps.stripe_core.webhook_delivery import DeliveryAssessment

        expected_url.return_value = "https://app.example.com/api/billing/webhook/"
        assess_delivery.return_value = DeliveryAssessment(
            projectSlug="webhook-app",
            expectedWebhookUrl=expected_url.return_value,
            deliveryStats=None,
            signatureProbe=None,
            needsRepair=False,
            repairReason=None,
            autoFixable=False,
        )
        stripe_client.WebhookEndpoint.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="we_123",
                    url="https://app.example.com/api/billing/webhook/",
                    status="enabled",
                    enabled_events=["checkout.session.completed"],
                )
            ]
        )
        stripe_client.Event.list.return_value = SimpleNamespace(data=[])

        result = webhook_health(self.project)

        self.assertTrue(result["healthy"])
        self.assertEqual(result["recentStripeEventCount"], 0)
        self.assertEqual(result["deliveryEvidence"]["status"], "inactive")
        self.assertIn("does not prove", result["deliveryEvidence"]["message"])

    @patch("apps.diagnostics.webhook_health.assess_webhook_delivery")
    @patch("apps.diagnostics.webhook_health.resolve_expected_webhook_url")
    @patch("apps.diagnostics.webhook_health.get_secret", return_value="sk_test_secret")
    @patch("apps.diagnostics.webhook_health.stripe")
    def test_event_read_error_marks_delivery_evidence_unknown(
        self, stripe_client, _get_secret, expected_url, assess_delivery
    ):
        from apps.stripe_core.webhook_delivery import DeliveryAssessment

        expected_url.return_value = "https://app.example.com/api/billing/webhook/"
        assess_delivery.return_value = DeliveryAssessment(
            projectSlug="webhook-app",
            expectedWebhookUrl=expected_url.return_value,
            deliveryStats=None,
            signatureProbe=None,
            needsRepair=False,
            repairReason=None,
            autoFixable=False,
        )
        stripe_client.WebhookEndpoint.list.return_value = SimpleNamespace(data=[])
        stripe_client.Event.list.side_effect = RuntimeError("stripe unavailable")

        result = webhook_health(self.project)

        self.assertIsNone(result["recentStripeEventCount"])
        self.assertEqual(result["deliveryEvidence"]["status"], "unknown")
