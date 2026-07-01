from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from apps.core.access import ProjectOwnedMixin
from apps.core.access import projects_for_user
from apps.runs.models import PipelineRun, PipelineRunLog
from apps.vault.models import ProjectVault, VaultSecret

from .client import SpecwrightUnavailable, fetch_dashboard, fetch_project_health
from .models import QualityProjectLink


class QualityLinkSerializer(serializers.Serializer):
    specwrightProjectId = serializers.IntegerField(min_value=1)
    specwrightProjectName = serializers.CharField(max_length=200, allow_blank=True, required=False)


class QualitySummaryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        try:
            dashboard = fetch_dashboard()
        except SpecwrightUnavailable as exc:
            return Response({"connected": False, "status": "unavailable", "message": str(exc)})

        summary = dashboard["summary"]
        return Response(
            {
                "connected": True,
                "status": "ready",
                "summary": {
                    "totalProjects": summary.get("total_projects", 0),
                    "scoredProjects": summary.get("scored_projects", 0),
                    "averageScore": summary.get("avg_score"),
                    "documentationCoverage": summary.get("avg_documentation_pct"),
                    "testCoverage": summary.get("avg_test_coverage_pct"),
                    "driftedThisWeek": summary.get("drifted_this_week", 0),
                    "needsAttention": summary.get("needs_attention", 0),
                },
                "projects": dashboard.get("projects", []),
            }
        )


class MigrationStatusView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        projects = projects_for_user(request.user).distinct()
        project_ids = list(projects.values_list("id", flat=True))
        runs = PipelineRun.objects.filter(project_id__in=project_ids)
        key_rows = VaultSecret.objects.filter(project_id__in=project_ids).values_list("project_id", "key_name")
        keys_by_project = {}
        for project_id, key_name in key_rows:
            keys_by_project.setdefault(project_id, set()).add(key_name)
        stripe_ready = sum(
            {"STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY"}.issubset(keys)
            for keys in keys_by_project.values()
        )
        railway_rows = []
        for project in projects.order_by("name"):
            keys = keys_by_project.get(project.id, set())
            railway = (project.scan_data or {}).get("railway") or {}
            project_id = "RAILWAY_PROJECT_ID" in keys or bool(railway.get("projectId"))
            service_id = "RAILWAY_SERVICE_ID" in keys or bool(railway.get("serviceId"))
            has_token = "RAILWAY_API_TOKEN" in keys
            railway_rows.append(
                {
                    "slug": project.slug,
                    "name": project.name,
                    "keyNames": sorted(keys),
                    "hasToken": has_token,
                    "hasProjectId": project_id,
                    "hasServiceId": service_id,
                    "ready": has_token and project_id and service_id,
                }
            )
        return Response(
            {
                "projects": projects.count(),
                "runs": runs.count(),
                "logs": PipelineRunLog.objects.filter(run__in=runs).count(),
                "vaults": ProjectVault.objects.filter(project_id__in=project_ids).count(),
                "secrets": VaultSecret.objects.filter(project_id__in=project_ids).count(),
                "stripeReadyProjects": stripe_ready,
                "railwayReadyProjects": sum(row["ready"] for row in railway_rows),
                "railwayProjects": railway_rows,
                "qualityLinks": QualityProjectLink.objects.filter(project_id__in=project_ids).count(),
            }
        )


class ProjectQualityLinkView(ProjectOwnedMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, project_slug):
        project = self.get_project(project_slug, min_role="viewer")
        link = QualityProjectLink.objects.filter(project=project).first()
        if not link:
            return Response({"linked": False})
        return Response({"linked": True, "specwrightProjectId": link.specwright_project_id, "specwrightProjectName": link.specwright_project_name})

    def put(self, request, project_slug):
        project = self.get_project(project_slug, min_role="member")
        serializer = QualityLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if QualityProjectLink.objects.filter(
            specwright_project_id=values["specwrightProjectId"]
        ).exclude(project=project).exists():
            raise serializers.ValidationError(
                {"specwrightProjectId": "This Specwright project is already linked."}
            )
        link, _ = QualityProjectLink.objects.update_or_create(
            project=project,
            defaults={
                "specwright_project_id": values["specwrightProjectId"],
                "specwright_project_name": values.get("specwrightProjectName", ""),
            },
        )
        return Response({"linked": True, "specwrightProjectId": link.specwright_project_id, "specwrightProjectName": link.specwright_project_name})

    def delete(self, request, project_slug):
        project = self.get_project(project_slug, min_role="member")
        QualityProjectLink.objects.filter(project=project).delete()
        return Response(status=204)


class ProjectQualityHealthView(ProjectOwnedMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, project_slug):
        project = self.get_project(project_slug, min_role="viewer")
        link = QualityProjectLink.objects.filter(project=project).first()
        if not link:
            return Response({"linked": False, "connected": False, "status": "not_linked"})
        try:
            health = fetch_project_health(link.specwright_project_id)
        except SpecwrightUnavailable as exc:
            return Response({"linked": True, "connected": False, "status": "unavailable", "message": str(exc)})

        score = health.get("score") or {}
        breakdown = score.get("breakdown") or {}
        gaps = score.get("gaps") or {}
        drift = health.get("drift") or {}
        return Response({
            "linked": True,
            "connected": True,
            "status": "ready",
            "specwrightProjectId": link.specwright_project_id,
            "score": score.get("score"),
            "grade": score.get("grade"),
            "summary": score.get("summary", ""),
            "documentationCoverage": breakdown.get("documentation_pct"),
            "testCoverage": breakdown.get("test_coverage_pct"),
            "freshness": breakdown.get("freshness_pct"),
            "routeCount": health.get("route_count", 0),
            "gaps": {"tests": gaps.get("no_test", 0), "documentation": gaps.get("no_docs", 0), "criticalRoutes": gaps.get("red_routes", 0)},
            "drift": {"detected": bool(drift.get("drift_detected", False)), "commitsBehind": drift.get("commits_behind", 0), "message": drift.get("message", "")},
            "lastScannedAt": health.get("last_scanned_at"),
        })
