from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.projects.api_keys import ProjectApiKey
from apps.projects.models import Project


class ProjectApiKeyTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="api-key-owner@example.com",
            password="test-pass-123",
        )
        self.project = Project.objects.create(owner=self.user, name="Keyed Project")
        self.other_project = Project.objects.create(owner=self.user, name="Other Project")
        self.client.force_authenticate(self.user)

    def test_key_lifecycle_is_project_scoped_and_revocable(self):
        create = self.client.post(
            f"/api/v1/projects/{self.project.slug}/api-keys/",
            {"name": "GitHub Actions"},
            format="json",
        )

        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        raw_key = create.data["key"]
        self.assertTrue(raw_key.startswith("si_"))
        self.assertFalse(ProjectApiKey.objects.filter(key_hash=raw_key).exists())

        listed = self.client.get(f"/api/v1/projects/{self.project.slug}/api-keys/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertNotIn("key", listed.data["keys"][0])

        project = ProjectApiKey.authenticate(raw_key)
        self.assertEqual(project, self.project)
        row = ProjectApiKey.objects.get(id=create.data["id"])
        self.assertIsNotNone(row.last_used_at)

        self.assertIsNone(ProjectApiKey.authenticate("si_not-a-real-key"))
        self.assertNotEqual(ProjectApiKey.authenticate(raw_key), self.other_project)

        revoked = self.client.delete(
            f"/api/v1/projects/{self.project.slug}/api-keys/{row.id}/"
        )
        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(ProjectApiKey.authenticate(raw_key))