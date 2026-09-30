import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.deploy.cloud_setup import catalog_entry_for, needs_cloud_setup, run_cloud_setup
from apps.projects.models import Project
from apps.runs.models import PipelineRun
from apps.vault.models import get_secret, set_secret

RAILWAY_VARS = {
    "STRIPE_SECRET_KEY": "sk_test_railway",
    "STRIPE_PUBLISHABLE_KEY": "pk_test_railway",
    "STRIPE_WEBHOOK_SECRET": "whsec_railway",
    "DATABASE_URL": "postgresql://u:p@db.internal.railway:5432/app",
    "DEBUG": "false",
}


@override_settings(VAULT_MASTER_KEY="c" * 64)
@patch.dict("os.environ", {"RAILWAY_API_TOKEN": "railway-token"})
@patch("apps.deploy.cloud_setup._health_check", return_value=(True, "HTTP 200"))
@patch("apps.deploy.cloud_setup._webhook_check", return_value=("pass", "registered"))
@patch("apps.deploy.env_push.get_railway_env_vars", return_value=dict(RAILWAY_VARS))
@patch("apps.deploy.env_push._railway_environment_id", return_value="env-1")
@patch("apps.deploy.railway_resolve.resolve_railway_service_by_host", return_value=("proj-1", "svc-1"))
class CloudSetupTests(TestCase):
    def setUp(self):
        # Keep vault mirrors out of the developer's real ~/.stripe-installer.
        data_dir = tempfile.TemporaryDirectory()
        self.addCleanup(data_dir.cleanup)
        env = patch.dict("os.environ", {"STRIPE_INSTALLER_DATA_DIR": data_dir.name})
        env.start()
        self.addCleanup(env.stop)
        self.user =get_user_model().objects.create_user(email="owner@example.com", password="test-pass-123")
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
        checks = run.result["readiness"]["checks"]
        self.assertTrue(checks)
        self.assertTrue(all(c["status"] == "pass" for c in checks))

    def test_never_overwrites_existing_vault_values(self, *_):
        set_secret(self.project, "STRIPE_SECRET_KEY", "sk_test_vault")

        run = run_cloud_setup(self.project, user=self.user)

        self.assertEqual(get_secret(self.project, "STRIPE_SECRET_KEY"), "sk_test_vault")
        self.assertNotIn("STRIPE_SECRET_KEY", run.result["importedKeys"])

    def test_missing_webhook_secret_is_reported(self, _resolve, _env, get_vars, *_):
        get_vars.return_value = {k: v for k, v in RAILWAY_VARS.items() if k != "STRIPE_WEBHOOK_SECRET"}

        run = run_cloud_setup(self.project, user=self.user)

        failing = [c["name"] for c in run.result["readiness"]["checks"] if c["status"] == "fail"]
        self.assertEqual(failing, ["Webhook signing secret"])
        self.assertLess(run.readiness_score, 100)

    def test_hand_added_project_matches_catalog_by_name(self, *_):
        duplicate = Project.objects.create(owner=self.user, name="Kistie Store", slug="kistie-store-1")
        self.assertEqual(catalog_entry_for(duplicate)["projectSlug"], "kistie-store")

    def test_deploy_run_endpoint_uses_cloud_setup(self, *_):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        # The catalog folder may exist on a developer machine; force the hosted-Studio path.
        with patch("apps.deploy.cloud_setup.needs_cloud_setup", return_value=True):
            response = client.post(f"/api/v1/projects/{self.project.slug}/deploy/run/", {}, format="json", secure=True)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], PipelineRun.Status.COMPLETED)
