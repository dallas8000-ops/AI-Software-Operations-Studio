"""Run read-only cloud setup for every active project of one owner."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.deploy.cloud_setup import run_cloud_setup
from apps.projects.models import Project
from apps.stripe_core.portfolio_catalog import HUB_SLUG
from apps.stripe_core.portfolio_register import portfolio_owner_email


class Command(BaseCommand):
    help = "Verify deployed apps from Railway/Stripe (read-only) and record setup runs."

    def add_arguments(self, parser):
        parser.add_argument("--owner-email", default=None)

    def handle(self, *args, **options):
        email = options["owner_email"] or portfolio_owner_email()
        owner = get_user_model().objects.filter(email__iexact=email).first()
        if not owner:
            raise CommandError(f"Owner not found: {email}")
        projects = Project.objects.filter(owner=owner, archived_at__isnull=True).exclude(slug=HUB_SLUG)
        for project in projects.order_by("slug"):
            run = run_cloud_setup(project, user=owner)
            checks = (run.result.get("readiness") or {}).get("checks") or []
            failing = [c["name"] for c in checks if c["status"] == "fail"]
            summary = f"score {run.readiness_score}" if run.readiness_score is not None else f"error: {run.error_message}"
            self.stdout.write(f"{project.slug:32} {summary}" + (f"  missing: {', '.join(failing)}" if failing else ""))
