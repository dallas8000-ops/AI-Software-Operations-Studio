from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase


class QualitySummaryTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(email="quality@example.com", password="test-pass-123")
        self.client.force_authenticate(user)

    @override_settings(SPECWRIGHT_API_URL="")
    def test_disconnected_adapter_degrades_safely(self):
        response = self.client.get("/api/v1/quality/summary/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["connected"])

    @patch("apps.quality.views.fetch_dashboard")
    def test_normalizes_specwright_dashboard(self, fetch_dashboard):
        fetch_dashboard.return_value = {
            "summary": {"total_projects": 3, "scored_projects": 2, "avg_score": 84, "needs_attention": 1},
            "projects": [{"id": 1, "name": "Example", "score": 84}],
        }
        response = self.client.get("/api/v1/quality/summary/", secure=True)
        self.assertTrue(response.data["connected"])
        self.assertEqual(response.data["summary"]["averageScore"], 84)
        self.assertEqual(response.data["summary"]["totalProjects"], 3)


class QualityProjectLinkTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="link@example.com", password="test-pass-123")
        self.other = get_user_model().objects.create_user(email="other@example.com", password="test-pass-123")
        from apps.projects.models import Project
        self.project = Project.objects.create(owner=self.user, name="Linked App")
        self.client.force_authenticate(self.user)

    def test_link_round_trip_without_touching_specwright(self):
        url = f"/api/v1/projects/{self.project.slug}/quality/link/"
        response = self.client.put(url, {"specwrightProjectId": 42, "specwrightProjectName": "Linked App"}, format="json", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(url, secure=True).data["specwrightProjectId"], 42)
        self.assertEqual(self.client.delete(url, secure=True).status_code, 204)
        self.assertFalse(self.client.get(url, secure=True).data["linked"])

    def test_other_user_cannot_read_link(self):
        url = f"/api/v1/projects/{self.project.slug}/quality/link/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url, secure=True).status_code, 404)

    @patch("apps.quality.views.fetch_project_health")
    def test_linked_project_health_is_normalized(self, fetch_health):
        from apps.quality.models import QualityProjectLink
        QualityProjectLink.objects.create(project=self.project, specwright_project_id=42)
        fetch_health.return_value = {
            "score": {"score": 88, "grade": "A", "summary": "Healthy", "breakdown": {"documentation_pct": 90, "test_coverage_pct": 80}, "gaps": {"no_test": 2}},
            "drift": {"drift_detected": False, "commits_behind": 0}, "route_count": 12,
        }
        response = self.client.get(f"/api/v1/projects/{self.project.slug}/quality/health/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["score"], 88)
        self.assertEqual(response.data["gaps"]["tests"], 2)
