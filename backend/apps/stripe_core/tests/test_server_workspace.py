"""The Studio never clones repos or reads local folders; readiness comes from Railway and live URLs."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.deploy.cloud_setup import needs_cloud_setup
from apps.projects import git_clone
from apps.projects.models import Project


class NoCloneTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(email="ws@example.com", password="pw-" + "x" * 12)
        self.project = Project.objects.create(
            owner=owner,
            name="EnPowerCommand",
            slug="enpowercommand",
            local_path=r"C:\Software Projects\EnPowerCommand",
            git_url="https://github.com/dallas8000-ops/EnPowerCommand.git",
        )

    def test_clone_helper_is_gone(self):
        self.assertFalse(hasattr(git_clone, "clone_to_server_workspace"))

    def test_readiness_never_uses_a_local_folder(self):
        self.assertTrue(needs_cloud_setup(self.project))
