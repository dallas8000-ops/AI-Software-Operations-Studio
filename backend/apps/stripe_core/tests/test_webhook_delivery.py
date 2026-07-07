"""Tests for webhook delivery monitoring and auto-repair."""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.projects.models import Project
from apps.stripe_core.webhook_delivery import (
    DeliveryStats,
    SignatureProbe,
    assess_webhook_delivery,
    fetch_delivery_stats,
)


class WebhookDeliveryStatsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="delivery@example.com",
            password="test-pass-123",
        )
        self.project = Project.objects.create(
            owner=self.user,
            slug="delivery-app",
            name="Delivery App",
            local_path="C:\\delivery-app",
        )

    @patch("apps.stripe_core.webhook_delivery.get_secret", return_value="sk_test_secret")
    @patch("apps.stripe_core.webhook_delivery.stripe")
    def test_fetch_delivery_stats_flags_high_failure_rate(self, stripe_client, _get_secret):
        stripe_client.Event.list.side_effect = [
            SimpleNamespace(data=[SimpleNamespace()] * 10),
            SimpleNamespace(data=[SimpleNamespace()] * 7),
        ]

        stats = fetch_delivery_stats(self.project, hours=24, min_sample=5)

        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats.totalEvents, 10)
        self.assertEqual(stats.failedDeliveries, 7)
        self.assertTrue(stats.highFailureRate)

    @patch("apps.stripe_core.webhook_delivery.is_stripe_exempt_slug", return_value=False)
    @patch("apps.stripe_core.webhook_delivery.probe_signed_webhook")
    @patch("apps.stripe_core.webhook_delivery.fetch_delivery_stats")
    @patch("apps.stripe_core.webhook_delivery.resolve_expected_webhook_url")
    def test_assess_marks_signature_mismatch_as_auto_fixable(
        self, expected_url, fetch_stats, probe, _exempt
    ):
        expected_url.return_value = "https://studio.example.com/api/v1/billing/webhook/"
        fetch_stats.return_value = DeliveryStats(
            lookbackHours=168,
            totalEvents=0,
            failedDeliveries=0,
            successRate=None,
            sampleSufficient=False,
            highFailureRate=False,
        )
        probe.return_value = SignatureProbe(
            url="https://studio.example.com/api/v1/billing/webhook/",
            httpStatus=400,
            classification="signature_mismatch",
            signatureValid=False,
            reachable=True,
            bodySnippet="Invalid payload",
        )

        assessment = assess_webhook_delivery(self.project)

        self.assertTrue(assessment.needsRepair)
        self.assertEqual(assessment.repairReason, "signature_mismatch")
        self.assertTrue(any(i["code"] == "webhook_signature_mismatch" for i in assessment.issues))

    @patch("apps.stripe_core.webhook_delivery.is_stripe_exempt_slug", return_value=False)
    @patch("apps.stripe_core.webhook_delivery.probe_signed_webhook", return_value=None)
    @patch("apps.stripe_core.webhook_delivery.fetch_delivery_stats")
    @patch("apps.stripe_core.webhook_delivery.resolve_expected_webhook_url")
    def test_assess_high_failure_rate_needs_repair(self, expected_url, fetch_stats, _probe, _exempt):
        expected_url.return_value = "https://studio.example.com/api/v1/billing/webhook/"
        fetch_stats.return_value = DeliveryStats(
            lookbackHours=168,
            totalEvents=10,
            failedDeliveries=7,
            successRate=0.3,
            sampleSufficient=True,
            highFailureRate=True,
        )

        assessment = assess_webhook_delivery(self.project)

        self.assertTrue(assessment.needsRepair)
        self.assertEqual(assessment.repairReason, "high_failure_rate")
