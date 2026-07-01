from django.contrib.auth import get_user_model
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
