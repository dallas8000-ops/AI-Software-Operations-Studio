from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.projects.models import Project


class ProjectListTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="portfolio-list@example.com", password="test-pass-123"
        )
        Project.objects.create(owner=self.user, name="Managed App", slug="managed-app")
        Project.objects.create(owner=self.user, name="SilverFox", slug="silverfox")
        self.client.force_authenticate(self.user)

    def test_portfolio_projects_are_available_only_when_requested(self):
        default_response = self.client.get("/api/v1/projects/", secure=True)
        complete_response = self.client.get(
            "/api/v1/projects/?include_portfolio=true", secure=True
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual([row["slug"] for row in default_response.data], ["managed-app"])
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(
            {row["slug"] for row in complete_response.data},
            {"managed-app", "silverfox"},
        )

    def test_archived_projects_are_hidden_by_default_and_can_be_restored(self):
        project = Project.objects.get(slug="managed-app")

        archive_response = self.client.post(
            f"/api/v1/projects/{project.slug}/archive/", {}, format="json", secure=True
        )
        default_response = self.client.get("/api/v1/projects/", secure=True)
        archived_response = self.client.get(
            "/api/v1/projects/?include_archived=true", secure=True
        )

        self.assertEqual(archive_response.status_code, 200)
        self.assertIsNotNone(archive_response.data["archived_at"])
        self.assertNotIn(project.slug, [row["slug"] for row in default_response.data])
        self.assertIn(project.slug, [row["slug"] for row in archived_response.data])
        self.assertTrue(
            project.audit_logs.filter(action="project.archived", actor=self.user).exists()
        )

        restore_response = self.client.post(
            f"/api/v1/projects/{project.slug}/restore/", {}, format="json", secure=True
        )
        self.assertEqual(restore_response.status_code, 200)
        self.assertIsNone(restore_response.data["archived_at"])
        self.assertTrue(
            project.audit_logs.filter(action="project.restored", actor=self.user).exists()
        )

    def test_archived_projects_cannot_be_seen_by_another_user(self):
        project = Project.objects.get(slug="managed-app")
        project.archived_at = timezone.now()
        project.save(update_fields=["archived_at"])
        other = get_user_model().objects.create_user(
            email="other@example.com", password="test-pass-123"
        )
        self.client.force_authenticate(other)

        response = self.client.post(
            f"/api/v1/projects/{project.slug}/restore/", {}, format="json", secure=True
        )

        self.assertEqual(response.status_code, 404)
