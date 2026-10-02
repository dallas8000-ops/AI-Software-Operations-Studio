from django.test import SimpleTestCase
from unittest import mock
from apps.deploy import cloud_setup as cs
from apps.stripe_core.webhook_delivery import SignatureProbe


class HonestProbeTests(SimpleTestCase):
    def test_json_body_reporting_error_fails_health(self):
        self.assertEqual(cs._reported_unhealthy('{"status": "error"}'), "status=error")
        self.assertEqual(cs._reported_unhealthy('{"status": "ok", "database": "down"}'), "database=down")

    def test_healthy_or_non_json_body_passes(self):
        self.assertEqual(cs._reported_unhealthy('{"status": "ok"}'), "")
        self.assertEqual(cs._reported_unhealthy("<html>ok</html>"), "")
        self.assertEqual(cs._reported_unhealthy("[1, 2]"), "")

    def _probe(self, classification, status):
        return SignatureProbe(url="https://x/w/", httpStatus=status, classification=classification,
                              signatureValid=classification == "ok", reachable=True)

    def test_signed_check_maps_probe_results(self):
        cases = {"ok": "pass", "signature_mismatch": "fail", "route_missing": "fail",
                 "handler_error": "fail", "unreachable": "warn", "csrf_blocked": "warn"}
        for kind, expected in cases.items():
            with mock.patch("apps.stripe_core.webhook_delivery.probe_signed_webhook",
                            return_value=self._probe(kind, 200)):
                self.assertEqual(cs._signed_webhook_check("https://x/w/", "whsec_abc")[0], expected, kind)

    def test_signed_check_rejects_non_whsec_secret(self):
        self.assertEqual(cs._signed_webhook_check("https://x/w/", "sk_nope")[0], "fail")
