from django.urls import path

from .views import DiagnoseView, FixView, OperationsReportView, ReadinessView

urlpatterns = [
    path("studio/operations-report/", OperationsReportView.as_view(), name="studio-operations-report"),
    path(
        "projects/<slug:project_slug>/diagnose/",
        DiagnoseView.as_view(),
        name="project-diagnose",
    ),
    path(
        "projects/<slug:project_slug>/readiness/",
        ReadinessView.as_view(),
        name="project-readiness",
    ),
    path(
        "projects/<slug:project_slug>/fix/",
        FixView.as_view(),
        name="project-fix",
    ),
]
