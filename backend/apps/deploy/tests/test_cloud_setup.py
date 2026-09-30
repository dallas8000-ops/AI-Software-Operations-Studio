from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.deploy.cloud_setup import catalog_entry_for, needs_cloud_setup, run_cloud_setup
from apps.projects.models import Project
from apps.runs.models import PipelineRun
from apps.runs.status import project_status
from apps.vault.models import get_secret, set_secret

RAILWAY_VARS = {
    "STRIPE_SECRET_KEY": "sk_test_railway",
    "STRIPE_PUBLISHABLE_KEY": "pk_test_railway",
    "STRIPE_WEBHOOK_SECRET": "whsec_railway",
    "DATABASE_URL": "postgresql://u:p@db.internal.railway:5432/app",
    "DEBUG": "false",
}


@patch.dict("os.environ", {"RAILWAY_API_TOKEN": "railway-token"})
@patch("apps.deploy.cloud_setup._health_check", return_value=(True, "HTTP 200"))
@patch("apps.deploy.cloud_setup._webhook_check", return_value=("pass", "registered"))
@patch("apps.deploy.env_push.get_railway_env_vars", return_value=dict(RAILWAY_VARS))
@patch("apps.deploy.env_push._railway_environment_id", return_value="env-1")
@patch("apps.deploy.railway_resolve.resolve_railway_service_by_host", return_value=("proj-1", "svc-1"))
class CloudSetupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="owner@example.com", password="test-pass-123")
        self.project = Project.objects.create(
            owner=self.user,
            name="Kistie Store",
            slug="kistie-store",
            local_path=r"C:\Software Projects\Kristie-Store-does-not-exist-here",
        )

    def test_missing_folder_triggers_cloud_setup(self, *_):
        self.assertTrue(needs_cloud_setup(self.project))

    def test_records_completed_ready_run_and_imports_keys(self, *_):
        run = run_cloud_setup(self.project, user=self.user)

        self.assertEqual(run.status, PipelineRun.Status.COMPLETED)
        self.assertEqual(run.readiness_score, 100)
        self.assertEqual(get_secret(self.project, "STRIPE_SECRET_KEY"), "sk_test_railway")
        self.assertIsNone(get_secret(self.project, "DEBUG"))
        self.assertEqual(project_status(run)["tone"], "ok")

    def test_never_overwrites_existing_vault_values(self, *_):
        set_secret(self.project, "STRIPE_SECRET_KEY", "sk_test_vault")

        run = run_cloud_setup(self.project, user=self.user)

        self.assertEqual(get_secret(self.project, "STRIPE_SECRET_KEY"), "sk_test_vault")
        self.assertNotIn("STRIPE_SECRET_KEY", run.result["importedKeys"])

    def test_missing_webhook_secret_is_reported(self, _resolve, _env, get_vars, *_):
        get_vars.return_value = {k: v for k, v in RAILWAY_VARS.items() if k != "STRIPE_WEBHOOK_SECRET"}

        run = run_cloud_setup(self.project, user=self.user)

        status = project_status(run)
        self.assertEqual(status["tone"], "fail")
        self.assertEqual(status["issues"][0]["name"], "Webhook signing secret")

    def test_hand_added_project_matches_catalog_by_name(self, *_):
        duplicate = Project.objects.create(owner=self.user, name="Kistie Store", slug="kistie-store-1")
        self.assertEqual(catalog_entry_for(duplicate)["projectSlug"], "kistie-store")

    def test_deploy_run_endpoint_uses_cloud_setup(self, *_):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/v1/projects/{self.project.slug}/deploy/run/", {}, format="json", secure=True)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], PipelineRun.Status.COMPLETED)
