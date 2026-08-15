"""Restore silverfox Studio vault to hearty-enjoyment hub Railway IDs."""

from __future__ import annotations

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apps.projects.models import Project  # noqa: E402
from apps.projects.scan_data_utils import update_project_scan_data  # noqa: E402
from apps.vault.models import get_secret, set_secret  # noqa: E402

HUB_PROJECT_ID = "e5dce2f2-ffc6-4677-8f16-d3912934cebd"
HUB_SILVERFOX_SERVICE_ID = "50b0bd07-66a2-436f-a654-a3262286d339"


def main() -> None:
    sf = Project.objects.get(slug="silverfox")
    before_pid = get_secret(sf, "RAILWAY_PROJECT_ID")
    before_sid = get_secret(sf, "RAILWAY_SERVICE_ID")
    set_secret(sf, "RAILWAY_PROJECT_ID", HUB_PROJECT_ID)
    set_secret(sf, "RAILWAY_SERVICE_ID", HUB_SILVERFOX_SERVICE_ID)
    update_project_scan_data(
        sf,
        {"railway": {"projectId": HUB_PROJECT_ID, "serviceId": HUB_SILVERFOX_SERVICE_ID}},
    )
    print("Restored silverfox vault to hearty-enjoyment hub:")
    print(f"  RAILWAY_PROJECT_ID: {before_pid} -> {HUB_PROJECT_ID}")
    print(f"  RAILWAY_SERVICE_ID: {before_sid} -> {HUB_SILVERFOX_SERVICE_ID}")


if __name__ == "__main__":
    main()
