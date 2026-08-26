"""Check why DBOps-Control-Center and SilverFox are FAILED."""
import os, sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()

from apps.projects.models import Project
from apps.stripe_core.setup_hub import setup_hub_status
from apps.deploy.preflight import run_deploy_preflight
from django.contrib.auth import get_user_model

user = get_user_model().objects.get(email="dallas8000@gmail.com")

for slug in ("dbops-control-center", "silverfox"):
    p = Project.objects.get(slug=slug, owner=user)
    print(f"\n{'='*50}")
    print(f"{slug.upper()}")
    print(f"{'='*50}")
    st = setup_hub_status(p, user=user)
    for s in st.get("steps", []):
        mark = "OK  " if s["ok"] else "TODO"
        detail = s.get("detail") or ""
        print(f"  [{mark}] {s['label']}")
        if not s["ok"] and detail:
            print(f"         {detail}")
    pf = run_deploy_preflight(p, push_railway_env=False, provision_postgres=False)
    if not pf.get("ok"):
        print(f"\n  Preflight issues:")
        for i in pf.get("issues") or []:
            print(f"    - {i}")
