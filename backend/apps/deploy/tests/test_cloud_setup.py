import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.deploy import cloud_setup
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
@patch("apps.deploy.cloud_setup._stripe_key_check", new=lambda key: ("pass", "accepted"))
@patch("apps.deploy.cloud_setup._webhook_check", return_value=("pass", "registered"))
@patch("apps.deploy.cloud_setup._signed_webhook_check", return_value=("pass", "accepted"))
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
            # A Stripe-billing catalog app (Kistie is Stripe-exempt on main).
            name="RIGHAND",
            slug="righand",
            local_path=r"C:\Software Projects\RigHand-does-not-exist-here",
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

    def test_missing_webhook_secret_is_reported(self, *_):
        without_whsec = {k: v for k, v in RAILWAY_VARS.items() if k != "STRIPE_WEBHOOK_SECRET"}
        with patch("apps.deploy.env_push.get_railway_env_vars", return_value=without_whsec):
            run = run_cloud_setup(self.project, user=self.user)

        self.assertEqual(run.error_message, "")
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

    def test_pipeline_run_button_and_readiness_use_cloud_setup(self, *_):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        base = f"/api/v1/projects/{self.project.slug}"
        with patch("apps.deploy.cloud_setup.needs_cloud_setup", return_value=True):
            run_response = client.post(f"{base}/runs/", {}, format="json", secure=True)
            readiness = client.get(f"{base}/deploy/readiness/", secure=True)
            stripe_cfg = client.get(f"{base}/stripe/config/", secure=True)

        self.assertEqual(run_response.status_code, 201)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.data["score"], 100)
        self.assertTrue(readiness.data["checks"])
        self.assertEqual(stripe_cfg.status_code, 200)
        # The frontend maps over these; an empty object blanks the project page.
        self.assertIsInstance(stripe_cfg.data["config"]["tiers"], list)
        with patch("apps.deploy.cloud_setup.needs_cloud_setup", return_value=True):
            deploy_cfg = client.get(f"{base}/deploy/config/", secure=True)
        self.assertEqual(deploy_cfg.status_code, 200)
        self.assertIn("provider", deploy_cfg.data["config"]["postgres"])

    def test_setup_hub_skips_repo_config_file_when_hosted(self, *_):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        with patch("apps.deploy.cloud_setup.needs_cloud_setup", return_value=True):
            response = client.get(f"/api/v1/projects/{self.project.slug}/setup-hub/", secure=True)

        self.assertEqual(response.status_code, 200)
        steps = {s["id"]: s for s in response.data["steps"] if "id" in s}
        self.assertTrue(steps["config"]["ok"])

    def test_readiness_button_runs_cloud_check(self, *_):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        with patch("apps.deploy.cloud_setup.needs_cloud_setup", return_value=True):
            response = client.get(f"/api/v1/projects/{self.project.slug}/readiness/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["score"], 100)
        self.assertTrue(response.data["checks"])

    def _database_check(self, variables, slug="righand"):
        self.project.slug = slug
        self.project.save()
        with patch("apps.deploy.env_push.get_railway_env_vars", return_value=variables):
            run = run_cloud_setup(self.project, user=self.user)
        return next(c for c in run.result["readiness"]["checks"] if c["id"] == "database")

    def test_app_prefixed_database_url_counts(self, *_):
        variables = {**RAILWAY_VARS, "SPECWRIGHT_DATABASE_URL": "sqlite+aiosqlite:////data/specwright.db"}
        del variables["DATABASE_URL"]
        check = self._database_check(variables)
        self.assertEqual(check["status"], "pass")
        self.assertIn("SPECWRIGHT_DATABASE_URL", check["message"])

    def test_sqlite_on_ephemeral_disk_warns(self, *_):
        variables = {**RAILWAY_VARS, "DATABASE_URL": "sqlite+aiosqlite:///specwright.db"}
        self.assertEqual(self._database_check(variables)["status"], "warn")

    def test_app_without_database_passes_when_optional(self, *_):
        variables = {k: v for k, v in RAILWAY_VARS.items() if k != "DATABASE_URL"}
        self.assertEqual(self._database_check(variables, slug="frontlinedigital")["status"], "pass")
        self.assertEqual(self._database_check(variables, slug="righand")["status"], "warn")


class AutoRepairTests(TestCase):
    def test_repairs_stray_prefix_before_scheme(self):
        from apps.deploy.cloud_setup import repaired_database_url

        self.assertEqual(repaired_database_url("URLpostgresql://u:p@h:5432/db"), "postgresql://u:p@h:5432/db")
        self.assertIsNone(repaired_database_url("postgresql://u:p@h:5432/db"))
        self.assertIsNone(repaired_database_url("not-a-url"))
        self.assertIsNone(repaired_database_url(""))

    def test_healthy_outcome_triggers_no_repairs(self):
        from apps.deploy.cloud_setup import _auto_repair

        outcome = {"checks": [{"id": "stripe_webhook", "status": "pass"}, {"id": "database", "status": "pass"}], "railway": {}}
        self.assertEqual(_auto_repair(None, outcome), [])

    def test_rejected_signing_secret_rotates_the_webhook(self):
        from apps.deploy import cloud_setup

        outcome = {
            "checks": [
                {"id": "stripe_webhook", "status": "pass"},
                {"id": "webhook_signature", "status": "fail", "message": "App rejected the signing secret held on Railway"},
            ],
            "railway": {},
        }
        with patch.object(cloud_setup, "get_secret", return_value="sk_test"), patch.object(
            cloud_setup, "register_webhook", return_value={"endpointId": "we_1"}
        ) as register:
            repairs = cloud_setup._auto_repair(None, outcome)
        register.assert_called_once()
        self.assertEqual(repairs[0]["repair"], "register_stripe_webhook")

    def test_missing_webhook_is_registered(self):
        from apps.deploy import cloud_setup

        outcome = {"checks": [{"id": "stripe_webhook", "status": "fail"}], "railway": {}}
        with patch.object(cloud_setup, "get_secret", return_value="sk_test"), patch.object(
            cloud_setup, "register_webhook", return_value={"endpointId": "we_1"}
        ) as register:
            repairs = cloud_setup._auto_repair(None, outcome)
        register.assert_called_once()
        self.assertEqual(repairs[0]["repair"], "register_stripe_webhook")
        self.assertTrue(repairs[0]["ok"])

class StripeCatalogTests(TestCase):
    def test_missing_products_detected_by_name(self):
        from apps.deploy import cloud_setup

        class P:
            def __init__(self, name):
                self.name = name

        class Listing:
            def auto_paging_iter(self):
                return iter([P("Starter")])

        with patch("stripe.Product.list", return_value=Listing()):
            missing = cloud_setup._missing_tier_products("sk", [{"name": "Starter"}, {"name": "Pro"}])
        self.assertEqual(missing, ["Pro"])

    def test_failed_catalog_triggers_provisioning(self):
        from apps.deploy import cloud_setup

        outcome = {"checks": [{"id": "stripe_catalog", "status": "fail"}], "railway": {}}
        with patch.object(cloud_setup, "provision_missing_catalog", return_value={"created": ["Pro"]}) as run:
            repairs = cloud_setup._auto_repair(None, outcome)
        run.assert_called_once()
        self.assertEqual(repairs[0]["repair"], "provision_stripe_catalog")

class StripeKeyCheckTests(TestCase):
    def test_rejected_key_fails(self):
        import stripe
        from apps.deploy import cloud_setup

        with patch("stripe.Balance.retrieve", side_effect=stripe.AuthenticationError("bad key")):
            self.assertEqual(cloud_setup._stripe_key_check("sk_test_x")[0], "fail")

    def test_accepted_key_passes(self):
        from apps.deploy import cloud_setup
        with patch("stripe.Balance.retrieve", return_value={}):
            self.assertEqual(cloud_setup._stripe_key_check("sk_test_x")[0], "pass")

    def test_network_error_is_only_a_warning(self):
        import stripe
        from apps.deploy import cloud_setup

        with patch("stripe.Balance.retrieve", side_effect=stripe.APIConnectionError("down")):
            self.assertEqual(cloud_setup._stripe_key_check("sk_test_x")[0], "warn")


class HealthBodyTests(TestCase):
    def test_database_false_is_unhealthy(self):
        self.assertTrue(cloud_setup._reported_unhealthy('{"ok": true, "db": false}'))
        self.assertTrue(cloud_setup._reported_unhealthy('{"ok": false}'))
        self.assertTrue(cloud_setup._reported_unhealthy('{"status": "ok", "database": "disconnected"}'))
        self.assertEqual(cloud_setup._reported_unhealthy('{"ok": true, "db": true}'), "")

    def test_web_page_on_health_path_fails(self):
        class Resp:
            status = 200
            headers = {"Content-Type": "text/html"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n):
                return b"<!doctype html><html></html>"

        with patch("urllib.request.urlopen", return_value=Resp()):
            ok, message = cloud_setup._health_check("https://x.example/health")
        self.assertFalse(ok)
        self.assertIn("web page", message)
