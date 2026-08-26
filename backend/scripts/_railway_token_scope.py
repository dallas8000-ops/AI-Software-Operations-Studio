"""Check current Railway token scope."""
import os, sys, json
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

HOME_ID = "e5dce2f2-ffc6-4677-8f16-d3912934cebd"

user = get_user_model().objects.get(email="dallas8000@gmail.com")
hub = Project.objects.get(slug="stripe-installer", owner=user)
token = get_secret(hub, "RAILWAY_API_TOKEN") or ""

print(f"Token prefix : {token[:8]}...{token[-4:] if len(token) > 12 else ''}")
print(f"Token length : {len(token)}")

# Account-level tokens can list all projects; project tokens cannot
try:
    data = _railway_gql(token, "query { projects { edges { node { id name } } } }")
    names = [e["node"]["name"] for e in (data.get("projects") or {}).get("edges", [])]
    print(f"\nScope: ACCOUNT-LEVEL — can enumerate all {len(names)} projects:")
    for n in sorted(names):
        print(f"  {n}")
except Exception as exc:
    if "Not Authorized" in str(exc) or "Unauthorized" in str(exc):
        print("\nScope: PROJECT-LEVEL — 'projects' query denied (expected for project tokens)")
    else:
        print(f"\n'projects' query error: {exc}")

# Either scope can access hearty-enjoyment directly
try:
    d2 = _railway_gql(token, "query($id: String!) { project(id: $id) { id name } }", {"id": HOME_ID})
    print(f"\nCan access hearty-enjoyment: YES — {d2.get('project', {}).get('name')}")
except Exception as exc:
    print(f"\nCan access hearty-enjoyment: NO — {exc}")
