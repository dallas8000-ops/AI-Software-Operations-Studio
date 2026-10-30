"""List Railway services that are not in the portfolio catalog (so none are missed)."""

from urllib.parse import urlparse

from django.core.management.base import BaseCommand

from apps.deploy.cloud_setup import _railway_token
from apps.deploy.railway_resolve import _own_project_with_domains
from apps.stripe_core.portfolio_catalog import PORTFOLIO_CATALOG
from apps.projects.models import Project

SKIP = ("postgres", "redis", "-db", "worker", "beat")


class Command(BaseCommand):
    help = "Show Railway services in this project that no catalog entry points at."

    def handle(self, *args, **options):
        project = Project.objects.first()
        token = _railway_token(project) if project else None
        if not token:
            self.stderr.write("No Railway token available.")
            return
        known = {urlparse(e["productionUrl"]).hostname for e in PORTFOLIO_CATALOG}
        for proj in _own_project_with_domains(token):
            for svc in proj["services"]:
                name = svc["name"].lower()
                if any(s in name for s in SKIP) or known & set(svc["domains"]):
                    continue
                self.stdout.write(f"UNLISTED {svc['name']}: {', '.join(svc['domains'][:2])}")
