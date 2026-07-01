from django.contrib.auth import get_user_model
from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.vault.models import set_secret


class SyncApprovalTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="sync@example.com",
            password="test-pass-123",
        )
        self.project = Project.objects.create(
            owner=self.user,
            name="Sync App",
            scan_data={"railway": {"projectId": "railway-project", "serviceId": "railway-service"}},
        )
        self.client.force_authenticate(self.user)
        with patch("apps.vault.models._apply_verification"):
            set_secret(self.project, "RAILWAY_API_TOKEN", "railway-token-secret")
            set_secret(self.project, "STRIPE_SECRET_KEY", "sk_test_secret")
            set_secret(self.project, "STRIPE_PUBLISHABLE_KEY", "pk_test_public")

    def test_sync_plan_exposes_names_not_values(self):
        response = self.client.get(
            f"/api/v1/projects/{self.project.slug}/deploy/sync-approval/",
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ready"])
        self.assertIn("STRIPE_SECRET_KEY", response.data["payload"]["keyNames"])
        rendered = str(response.data)
        self.assertNotIn("railway-token-secret", rendered)
        self.assertNotIn("sk_test_secret", rendered)
        self.assertNotIn("pk_test_public", rendered)

    def test_apply_requires_exact_confirmation(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.slug}/deploy/sync-approval/",
            {"confirmation": "yes"},
            format="json",
            secure=True,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["requiresConfirmation"],
            f"SYNC {self.project.slug} TO RAILWAY",
        )
