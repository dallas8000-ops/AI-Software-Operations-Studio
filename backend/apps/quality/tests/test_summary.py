from unittest.mock import patch
import json
import sqlite3
import tempfile
from pathlib import Path

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

    def test_migration_status_counts_owned_project_data(self):
        from apps.runs.models import PipelineRun, PipelineRunLog
        from apps.vault.models import ProjectVault, VaultSecret

        run = PipelineRun.objects.create(project=self.project, started_by=self.user, status="completed")
        PipelineRunLog.objects.create(run=run, step="verify", status="ok", message="done")
        ProjectVault.objects.create(project=self.project, salt=b"x" * 32)
        for key in (
            "STRIPE_SECRET_KEY",
            "STRIPE_PUBLISHABLE_KEY",
            "RAILWAY_API_TOKEN",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID",
        ):
            VaultSecret.objects.create(project=self.project, key_name=key, encrypted_value="x", iv="x", auth_tag="x")
        response = self.client.get("/api/v1/studio/migration-status/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["projects"], 1)
        self.assertEqual(response.data["runs"], 1)
        self.assertEqual(response.data["logs"], 1)
        self.assertEqual(response.data["stripeReadyProjects"], 1)
        self.assertEqual(response.data["railwayReadyProjects"], 1)
        self.assertEqual(response.data["railwayProjects"][0]["slug"], self.project.slug)
        self.assertIn("STRIPE_SECRET_KEY", response.data["railwayProjects"][0]["keyNames"])
        self.assertNotIn("value", response.data["railwayProjects"][0])


class SpecwrightSqliteFallbackTests(APITestCase):
    def test_reads_dashboard_and_project_health_without_fastapi(self):
        from apps.quality.client import fetch_dashboard, fetch_project_health

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "specwright.db"
            db = sqlite3.connect(path)
            db.executescript(
                """
                CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT, root_path TEXT, framework TEXT,
                  watch_enabled INTEGER, github_repo TEXT, last_score INTEGER);
                CREATE TABLE scans (id INTEGER PRIMARY KEY, project_id INTEGER, status TEXT, stats TEXT, created_at TEXT);
                """
            )
            stats = {"score": {"score": 91, "grade": "A", "breakdown": {"documentation_pct": 95, "test_coverage_pct": 87}, "gaps": {}}, "routes_found": 14, "drift": {"drift_detected": False}}
            db.execute("INSERT INTO projects VALUES (1, 'Example', 'C:/Example', 'auto', 0, 'org/example', 91)")
            db.execute("INSERT INTO scans VALUES (1, 1, 'completed', ?, '2026-06-30T12:00:00')", (json.dumps(stats),))
            db.commit(); db.close()
            with override_settings(SPECWRIGHT_API_URL="", SPECWRIGHT_SQLITE_PATH=str(path)):
                dashboard = fetch_dashboard()
                health = fetch_project_health(1)
            self.assertEqual(dashboard["summary"]["avg_score"], 91)
            self.assertEqual(health["score"]["score"], 91)
