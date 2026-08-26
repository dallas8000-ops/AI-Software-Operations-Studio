"""Check Railway token access for all FAILED projects."""
import os, sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()

from apps.projects.models import Project
from apps.vault.models import get_secret
from apps.deploy.env_push import _railway_gql
from django.contrib.auth import get_user_model

CHECKS = {
    "ai-memory-engine":      "bdca8d7b-2387-4b8a-8278-ff2e6ddb96b8",
    "dbops-control-center":  None,  # look up from scan_data
    "silverfox":             None,
}

user = get_user_model().objects.get(email="dallas8000@gmail.com")

for slug, project_id in CHECKS.items():
    p = Project.objects.get(slug=slug, owner=user)
    token = get_secret(p, "RAILWAY_API_TOKEN") or ""
    sd = p.scan_data or {}
    if not project_id:
        project_id = (sd.get("railway") or {}).get("projectId") or ""

    prefix = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else token or "(none)"
    if not token:
        print(f"[!!] {slug}: no RAILWAY_API_TOKEN in vault")
        continue
    if not project_id:
        print(f"[??] {slug}: no projectId in scan_data")
        continue

    try:
        data = _railway_gql(token, "query($id: String!) { project(id: $id) { id name } }", {"id": project_id})
        name = (data.get("project") or {}).get("name", "?")
        print(f"[OK] {slug}: token {prefix} -> Railway project '{name}'")
    except Exception as exc:
        print(f"[!!] {slug}: token {prefix} -> {exc}")
