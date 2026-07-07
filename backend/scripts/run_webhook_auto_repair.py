"""Run webhook delivery auto-repair for billing projects."""
from __future__ import annotations

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.core.access import projects_for_user  # noqa: E402
from apps.projects.models import Project  # noqa: E402
from apps.stripe_core.hub_keys import get_hub_project, HUB_SLUG  # noqa: E402
from apps.stripe_core.portfolio_catalog import is_stripe_exempt_slug  # noqa: E402
from apps.stripe_core.portfolio_sync import sync_portfolio_registry  # noqa: E402
from apps.stripe_core.secret_placement import repair_project_secret_placement  # noqa: E402
from apps.stripe_core.webhook_delivery import assess_and_repair_if_needed, assess_webhook_delivery  # noqa: E402
from apps.vault.models import VaultSecret  # noqa: E402


def main() -> None:
    slug_filter = sys.argv[1] if len(sys.argv) > 1 else None
    user = get_user_model().objects.filter(email="dallas8000@gmail.com").first()
    if user:
        sync_portfolio_registry(list(projects_for_user(user)))
        print("Synced portfolio registry from catalog")

    if slug_filter:
        project_ids = list(
            Project.objects.filter(slug=slug_filter).values_list("id", flat=True)
        )
    else:
        project_ids = (
            VaultSecret.objects.filter(key_name="STRIPE_SECRET_KEY")
            .values_list("project_id", flat=True)
            .distinct()
        )

    projects = [Project.objects.get(id=pid) for pid in project_ids]
    print(f"Found {len(projects)} billing project(s)")

    hub = get_hub_project(user) if user else None

    for project in projects:
        if is_stripe_exempt_slug(project.slug):
            print(f"  skip exempt: {project.slug}")
            continue

        assessment = assess_webhook_delivery(project)
        stats = assessment.deliveryStats
        probe = assessment.signatureProbe
        expected = assessment.expectedWebhookUrl
        rate = (
            f"{round((stats.successRate or 0) * 100, 1)}%"
            if stats and stats.successRate is not None
            else "n/a"
        )
        probe_class = probe.classification if probe else None
        print(
            f"  {project.slug}: url={expected} needsRepair={assessment.needsRepair} "
            f"reason={assessment.repairReason} successRate={rate} probe={probe_class}"
        )

        if project.slug == HUB_SLUG or assessment.needsRepair:
            print("    -> running secret placement repair...")
            placement = repair_project_secret_placement(project, hub=hub)
            print(f"    -> placement ok={placement.get('ok')}")

        if not assessment.needsRepair and project.slug != HUB_SLUG:
            continue

        print("    -> running delivery auto-repair...")
        result = assess_and_repair_if_needed(project)
        after = (result.get("repair") or {}).get("assessmentAfter") or {}
        probe_after = (after.get("signatureProbe") or {}).get("classification")
        after_url = after.get("expectedWebhookUrl")
        print(
            f"    -> ok={result.get('ok')} repaired={result.get('repaired')} "
            f"urlAfter={after_url} probeAfter={probe_after}"
        )

    print("Done.")


if __name__ == "__main__":
    main()
