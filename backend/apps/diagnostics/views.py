from pathlib import Path

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.access import ProjectOwnedMixin
from apps.deploy.postgres import get_production_url
from apps.projects.models import Project
from apps.stripe_core.readiness import readiness_label, run_readiness_checks, score_readiness
from apps.stripe_core.repair import run_auto_fix, run_repair_action

from .diagnostics import run_diagnostics


class OperationsReportView(APIView):
    """Account-wide, secret-free operational report for the Version 2 control center."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        from datetime import timedelta

        from django.utils import timezone

        from apps.core.access import projects_for_user
        from apps.organizations.models import Membership
        from apps.projects.models import AuditLog
        from apps.runs.models import PipelineRun
        from apps.stripe_core.hub_keys import resolve_production_app_url

        projects = list(projects_for_user(request.user).distinct().select_related("organization"))
        project_ids = [project.id for project in projects]
        runs = PipelineRun.objects.filter(project_id__in=project_ids).select_related("project")
        since = timezone.now() - timedelta(hours=24)
        latest_by_project = {}
        for run in runs.order_by("project_id", "-created_at"):
            latest_by_project.setdefault(run.project_id, run)

        rows = []
        for project in projects:
            latest = latest_by_project.get(project.id)
            score = latest.readiness_score if latest and latest.readiness_score is not None else (
                project.scan_data or {}
            ).get("lastReadinessScore")
            rows.append(
                {
                    "slug": project.slug,
                    "name": project.name,
                    "organization": project.organization.name if project.organization_id else None,
                    "archived": project.archived_at is not None,
                    "readinessScore": score,
                    "lastRunStatus": latest.status if latest else None,
                    "lastRunAt": latest.created_at.isoformat() if latest else None,
                    "productionUrl": resolve_production_app_url(project),
                }
            )

        active_rows = [row for row in rows if not row["archived"]]
        scores = [row["readinessScore"] for row in active_rows if isinstance(row["readinessScore"], int)]
        memberships = Membership.objects.filter(user=request.user).select_related("organization")
        organization_ids = list(memberships.values_list("organization_id", flat=True))
        github_connected = memberships.filter(
            organization__github_installation_id__isnull=False
        ).values("organization_id").distinct().count()

        activity = [
            {
                "project": log.project.name,
                "projectSlug": log.project.slug,
                "action": log.action,
                "actor": log.actor.email if log.actor else None,
                "createdAt": log.created_at.isoformat(),
            }
            for log in AuditLog.objects.filter(project_id__in=project_ids)
            .select_related("project", "actor")[:20]
        ]

        failed_recently = runs.filter(status=PipelineRun.Status.FAILED, created_at__gte=since)
        recovery = []
        for failed in failed_recently.order_by("-created_at")[:10]:
            previous_success = runs.filter(
                project=failed.project,
                status=PipelineRun.Status.COMPLETED,
                created_at__lte=failed.created_at,
            ).exclude(pk=failed.pk).order_by("-created_at").first()
            recovery.append(
                {
                    "project": failed.project.name,
                    "projectSlug": failed.project.slug,
                    "failedRunId": str(failed.id),
                    "failedAt": failed.created_at.isoformat(),
                    "error": failed.error_message[:240],
                    "previousSuccessfulRunId": str(previous_success.id) if previous_success else None,
                    "recoveryAvailable": previous_success is not None,
                }
            )

        return Response(
            {
                "generatedAt": timezone.now().isoformat(),
                "summary": {
                    "projects": len(active_rows),
                    "archivedProjects": len(rows) - len(active_rows),
                    "averageReadiness": round(sum(scores) / len(scores)) if scores else None,
                    "readyProjects": sum(1 for score in scores if score >= 90),
                    "needsAttention": sum(1 for score in scores if score < 90),
                    "running": runs.filter(status=PipelineRun.Status.RUNNING).count(),
                    "failed24h": failed_recently.count(),
                    "deployments24h": runs.filter(created_at__gte=since).count(),
                    "organizations": len(set(organization_ids)),
                    "githubConnectedOrganizations": github_connected,
                },
                "projects": sorted(rows, key=lambda row: (row["archived"], row["name"].lower())),
                "recentActivity": activity,
                "recoveryCandidates": recovery,
            }
        )


def _require_local_path(project: Project) -> Path:
    if not project.local_path:
        raise ValueError("Set project local_path first.")
    root = Path(project.local_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project path not found: {root}")
    return root


class DiagnoseView(ProjectOwnedMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, project_slug: str):
        project = self.get_project(project_slug)
        try:
            root = _require_local_path(project)
        except (ValueError, FileNotFoundError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        report = run_diagnostics(project, root)
        scan_data = dict(project.scan_data or {})
        scan_data["lastHealthScore"] = report.health_score
        scan_data["lastDiagnosedAt"] = report.scanned_at
        project.scan_data = scan_data
        project.save(update_fields=["scan_data", "updated_at"])
        return Response(report.to_dict())


class ReadinessView(ProjectOwnedMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, project_slug: str):
        project = self.get_project(project_slug)
        try:
            root = _require_local_path(project)
        except (ValueError, FileNotFoundError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        app_url = (
            request.query_params.get("app_url")
            or get_production_url(project, "")
            or request.build_absolute_uri("/").rstrip("/")
        )
        checks = run_readiness_checks(project, root, production_url=app_url)
        score = score_readiness(checks)
        scan_data = dict(project.scan_data or {})
        scan_data["lastReadinessScore"] = score
        scan_data["lastReadinessLabel"] = readiness_label(score)
        project.scan_data = scan_data
        project.save(update_fields=["scan_data", "updated_at"])
        return Response(
            {
                "score": score,
                "label": readiness_label(score),
                "checks": [c.to_dict() for c in checks],
            }
        )


class FixView(ProjectOwnedMixin, APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, project_slug: str):
        project = self.get_project(project_slug)
        try:
            _require_local_path(project)
        except (ValueError, FileNotFoundError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data or {}
        action = data.get("action")
        issue_ids = data.get("issue_ids") or data.get("issueIds")
        force = bool(data.get("force"))
        app_url = data.get("app_url") or request.build_absolute_uri("/").rstrip("/")

        if action:
            try:
                repair = run_repair_action(project, action, force=force, app_url=app_url)
                report = run_diagnostics(project, Path(project.local_path).resolve())
                return Response(
                    {
                        "repairs": [repair.to_dict()],
                        "report": report.to_dict(),
                    }
                )
            except Exception as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if data.get("all"):
            repairs, report = run_auto_fix(project, force=force, app_url=app_url)
        else:
            repairs, report = run_auto_fix(
                project,
                issue_ids=issue_ids,
                force=force,
                app_url=app_url,
            )

        return Response(
            {
                "repairs": [r.to_dict() for r in repairs],
                "report": report.to_dict(),
            }
        )
