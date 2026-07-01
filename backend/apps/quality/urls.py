from django.urls import path

from .views import MigrationStatusView, ProjectQualityHealthView, ProjectQualityLinkView, QualitySummaryView

urlpatterns = [
    path("quality/summary/", QualitySummaryView.as_view(), name="quality-summary"),
    path("studio/migration-status/", MigrationStatusView.as_view(), name="studio-migration-status"),
    path("projects/<slug:project_slug>/quality/link/", ProjectQualityLinkView.as_view(), name="project-quality-link"),
    path("projects/<slug:project_slug>/quality/health/", ProjectQualityHealthView.as_view(), name="project-quality-health"),
]
