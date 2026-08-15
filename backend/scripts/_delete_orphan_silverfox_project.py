"""Delete orphan Railway project created by failed silverfox split."""

from __future__ import annotations

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apps.deploy.railway_consolidate import _find_project, _project_delete  # noqa: E402
from apps.deploy.railway_resolve import _list_railway_projects_with_domains  # noqa: E402
from apps.projects.models import Project  # noqa: E402
from apps.stripe_core.portfolio_catalog import HUB_SLUG  # noqa: E402
from apps.vault.models import get_secret  # noqa: E402

ORPHAN_PROJECT_ID = "4bd8b79c-9479-4c01-8855-bfe98dec063f"
ORPHAN_PROJECT_NAME = "silverfox"
HUB_PROJECT_ID = "e5dce2f2-ffc6-4677-8f16-d3912934cebd"


def main() -> None:
    hub = Project.objects.get(slug=HUB_SLUG)
    token = get_secret(hub, "RAILWAY_API_TOKEN")
    if not token:
        raise SystemExit("RAILWAY_API_TOKEN missing")

    project = _find_project(_list_railway_projects_with_domains(token), ORPHAN_PROJECT_NAME)
    if not project:
        print(f"Project '{ORPHAN_PROJECT_NAME}' not found — already deleted.")
        return

    project_id = str(project.get("id") or "")
    if project_id != ORPHAN_PROJECT_ID:
        raise SystemExit(f"Refusing: project id {project_id} != expected orphan {ORPHAN_PROJECT_ID}")
    if project_id == HUB_PROJECT_ID:
        raise SystemExit("Refusing: would delete hearty-enjoyment hub")

    services = [s.get("name") for s in project.get("services") or []]
    print(f"Deleting orphan Railway project '{ORPHAN_PROJECT_NAME}' ({project_id})")
    print(f"  Services: {', '.join(services) or '(none)'}")
    _project_delete(token, project_id)
    print("Deleted.")


if __name__ == "__main__":
    main()
