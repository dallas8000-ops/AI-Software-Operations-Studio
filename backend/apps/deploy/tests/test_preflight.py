from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
import tempfile
from pathlib import Path

from apps.deploy.preflight import run_deploy_preflight
from apps.projects.models import Project


class DeployPreflightTests(TestCase):
    def test_blocks_missing_railway_token(self):
        User = get_user_model()
        user = User.objects.create_user(email="preflight@test.local", password="pass12345")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "railway.toml").write_text("", encoding="utf-8")
            project = Project.objects.create(
                owner=user,
                name="Test",
                slug="preflight-test",
                local_path=str(root),
                scan_data={"deployPlatform": "railway"},
            )
            from unittest.mock import patch

            with patch("apps.deploy.preflight.hydrate_project_vault"):
                with patch("apps.deploy.preflight.vault_health", return_value={"unreadableCount": 0, "totalCount": 0}):
                    with patch("apps.deploy.preflight.get_secret", return_value=None):
                        result = run_deploy_preflight(project, push_railway_env=True, provision_stripe=False)
        self.assertFalse(result["ok"])
        self.assertTrue(any("RAILWAY_API_TOKEN" in i for i in result["issues"]))

    def test_warns_when_railway_list_empty(self):
        User = get_user_model()
        user = User.objects.create_user(email="preflight2@test.local", password="pass12345")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "railway.toml").write_text("", encoding="utf-8")
            project = Project.objects.create(
                owner=user,
                name="SilverFox",
                slug="preflight-silverfox",
                local_path=str(root),
                scan_data={"deployPlatform": "railway"},
            )

            def fake_get_secret(proj, key):
                if key == "RAILWAY_API_TOKEN":
                    return "token"
                return None

            from unittest.mock import patch

            with patch("apps.deploy.preflight.hydrate_project_vault"):
                with patch("apps.deploy.preflight.vault_health", return_value={"unreadableCount": 0, "totalCount": 1}):
                    with patch("apps.deploy.preflight.get_secret", side_effect=fake_get_secret):
                        with patch("apps.deploy.preflight.resolve_railway_project_id", return_value=None):
                            with patch("apps.deploy.preflight._list_railway_projects", return_value=[]):
                                result = run_deploy_preflight(project, push_railway_env=True, provision_stripe=False)
        self.assertTrue(any("returned no projects" in w for w in result["warnings"]))


class WorkspaceMissingResponseTests(SimpleTestCase):
    def test_missing_folder_is_a_clear_409_not_a_500(self):
        from apps.deploy.errors import workspace_missing_response

        resp = workspace_missing_response(
            FileNotFoundError(r"Project folder not found: C:\Software Projects\EnPowerCommand.")
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["code"], "workspace_missing")
        self.assertIn("EnPowerCommand", resp.data["error"])
        self.assertIn("Studio on the computer", resp.data["error"])
