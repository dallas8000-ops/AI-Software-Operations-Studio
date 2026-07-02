from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import AuditLog, Project
from apps.runs.models import PipelineRun


class OperationsReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="ops-report@example.com", password="test-pass-123"
        )
        self.project = Project.objects.create(
            owner=self.user,
            name="Ready App",
            slug="ready-app",
            scan_data={"lastReadinessScore": 94},
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_report_aggregates_projects_runs_and_activity(self):
        PipelineRun.objects.create(
            project=self.project,
            started_by=self.user,
            status=PipelineRun.Status.COMPLETED,
            readiness_score=96,
        )
        AuditLog.objects.create(
            project=self.project, actor=self.user, action="project.scanned"
        )

        response = self.client.get("/api/v1/studio/operations-report/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["projects"], 1)
        self.assertEqual(response.data["summary"]["averageReadiness"], 96)
        self.assertEqual(response.data["summary"]["readyProjects"], 1)
        self.assertEqual(response.data["projects"][0]["lastRunStatus"], "completed")
        self.assertEqual(response.data["recentActivity"][0]["action"], "project.scanned")

    def test_report_exposes_recovery_candidate_without_secret_data(self):
        completed = PipelineRun.objects.create(
            project=self.project,
            started_by=self.user,
            status=PipelineRun.Status.COMPLETED,
        )
        failed = PipelineRun.objects.create(
            project=self.project,
            started_by=self.user,
            status=PipelineRun.Status.FAILED,
            error_message="Release health check failed",
        )

        response = self.client.get("/api/v1/studio/operations-report/", secure=True)

        self.assertEqual(response.data["summary"]["failed24h"], 1)
        recovery = response.data["recoveryCandidates"][0]
        self.assertEqual(recovery["failedRunId"], str(failed.id))
        self.assertEqual(recovery["previousSuccessfulRunId"], str(completed.id))
        self.assertTrue(recovery["recoveryAvailable"])
