"""Hosted Studio: full setup clones the app repo instead of requiring a local disk path."""

import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.projects.models import Project
from apps.stripe_core.portfolio_workspace import ensure_project_workspace, require_project_folder
from apps.stripe_core.portfolio_catalog import HUB_SLUG
from apps.stripe_core import portfolio_workspace


def _owner():
    return get_user_model().objects.create_user(email="ws@example.com", password="x-long-test-password")


class ServerWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = _owner()
        self.project = Project.objects.create(
            owner=self.owner,
            name="EnPowerCommand",
            slug="enpowercommand",
            local_path=r"C:\Software Projects\EnPowerCommand",
            git_url="https://github.com/dallas8000-ops/EnPowerCommand.git",
        )

    @override_settings(SERVER_WORKSPACES_ENABLED=False)
    def test_local_mode_still_requires_the_folder(self):
        with self.assertRaises(FileNotFoundError):
            require_project_folder(self.project)

    @override_settings(SERVER_WORKSPACES_ENABLED=True)
    def test_hosted_mode_clones_when_folder_missing(self):
        with mock.patch("apps.projects.git_clone.clone_to_server_workspace", return_value=Path("/srv/x")) as clone:
            self.assertEqual(require_project_folder(self.project), Path("/srv/x"))
        clone.assert_called_once_with(self.project)

    @override_settings(SERVER_WORKSPACES_ENABLED=True)
    def test_hosted_mode_without_git_url_still_raises(self):
        self.project.git_url = ""
        self.project.save()
        with self.assertRaises(FileNotFoundError):
            require_project_folder(self.project)

    @override_settings(SERVER_WORKSPACES_ENABLED=True)
    def test_hosted_hub_points_at_deployed_code(self):
        hub = Project.objects.create(
            owner=self.owner, name="Hub", slug=HUB_SLUG,
            local_path=r"C:\Software Projects\AI Software Operations Studio",
        )
        path, changed = ensure_project_workspace(hub)
        self.assertTrue(changed)
        self.assertEqual(path, str(portfolio_workspace.HUB_REPO_ROOT))
        hub.refresh_from_db()
        self.assertEqual(hub.local_path, str(portfolio_workspace.HUB_REPO_ROOT))

    def test_clone_to_server_workspace_real_git(self):
        from apps.projects import git_clone

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            for cmd in (["git", "init", "-q"], ["git", "-c", "user.email=a@b", "-c", "user.name=a",
                        "commit", "-q", "--allow-empty", "-m", "init"]):
                subprocess.run(cmd, cwd=src, check=True)
            ws = Path(tmp) / "ws"
            real_run = subprocess.run

            def fake_run(args, **kw):
                # Swap the https URL for the local repo; everything else is real git.
                args = [str(src) if a.startswith("https://") else a for a in args]
                return real_run(args, **kw)

            with override_settings(PROJECT_WORKSPACE_ROOT=ws), mock.patch.object(git_clone.subprocess, "run", fake_run):
                dest = git_clone.clone_to_server_workspace(self.project)
                self.assertTrue((dest / ".git").is_dir())
                self.project.refresh_from_db()
                self.assertEqual(self.project.local_path, str(dest))
                # Second call updates in place instead of failing.
                self.assertEqual(git_clone.clone_to_server_workspace(self.project), dest)
