"""Revoke old Railway token and create a new project-scoped one."""
import os, sys, json
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()

from apps.projects.models import Project
from apps.vault.models import get_secret, set_secret
from apps.deploy.env_push import _railway_gql, _railway_environment_id
from django.contrib.auth import get_user_model

OLD_TOKEN_ID = "45b173cd-f17b-41aa-8054-504c39b550b0"
HOME_PROJECT_ID = "e5dce2f2-ffc6-4677-8f16-d3912934cebd"

user = get_user_model().objects.get(email="dallas8000@gmail.com")
hub = Project.objects.get(slug="stripe-installer", owner=user)
current_token = get_secret(hub, "RAILWAY_API_TOKEN") or ""

print(f"Current token: {current_token[:8]}...{current_token[-4:]}")

env_id = _railway_environment_id(current_token, HOME_PROJECT_ID)
print(f"Production environment ID: {env_id}")

# Step 1: Try to create a new project-scoped token first (so we're never locked out)
print("\n--- Creating new project-scoped token ---")
try:
    result = _railway_gql(
        current_token,
        """
        mutation($input: ProjectTokenCreateInput!) {
          projectTokenCreate(input: $input)
        }
        """,
        {"input": {"projectId": HOME_PROJECT_ID, "environmentId": env_id, "name": "automation-center-deploy"}},
    )
    new_token = result.get("projectTokenCreate") or ""
    if new_token:
        print(f"New project token created: {new_token[:8]}...{new_token[-4:]}")
    else:
        print(f"Unexpected response: {json.dumps(result, indent=2)}")
        sys.exit(1)
except Exception as exc:
    print(f"projectTokenCreate failed: {exc}")
    # Try personal access token as fallback
    print("\n--- Trying personalAccessTokenCreate as fallback ---")
    try:
        result = _railway_gql(
            current_token,
            """
            mutation($input: ApiTokenCreateInput!) {
              apiTokenCreate(input: $input)
            }
            """,
            {"input": {"name": "automation-center-deploy"}},
        )
        new_token = result.get("apiTokenCreate") or ""
        if new_token:
            print(f"New personal token created: {new_token[:8]}...{new_token[-4:]}")
        else:
            print(f"Unexpected response: {json.dumps(result, indent=2)}")
            sys.exit(1)
    except Exception as exc2:
        print(f"personalAccessTokenCreate also failed: {exc2}")
        sys.exit(1)

# Step 2: Update all project vaults with the new token
print("\n--- Updating all project vaults ---")
for p in Project.objects.filter(owner=user):
    set_secret(p, "RAILWAY_API_TOKEN", new_token)
    print(f"  updated: {p.slug}")

# Step 3: Revoke the old token
print(f"\n--- Revoking old token {OLD_TOKEN_ID} ---")
try:
    result = _railway_gql(
        new_token,  # use new token to revoke the old one
        """
        mutation($id: String!) {
          apiTokenDelete(id: $id)
        }
        """,
        {"id": OLD_TOKEN_ID},
    )
    print(f"Revoked: {result}")
except Exception as exc:
    # Old token ID may not match this mutation — may need dashboard
    print(f"Revoke via API failed (may need dashboard): {exc}")
    print(f"Manually revoke at: https://railway.com/account/tokens")

print("\nDone. Run _railway_token_scope.py to verify.")
