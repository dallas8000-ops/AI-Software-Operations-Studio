"""Trigger pipeline runs for dbops-control-center and digital-sales-automation-center."""
import os, sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()

from apps.runs.tasks import execute_pipeline
from apps.runs.models import PipelineRun
from apps.projects.models import Project
from django.contrib.auth import get_user_model

user = get_user_model().objects.get(email="dallas8000@gmail.com")

for slug in ("dbops-control-center", "digital-sales-automation-center"):
    p = Project.objects.get(slug=slug, owner=user)
    print(f"\nRunning pipeline for {p.name}...")
    run = PipelineRun.objects.create(project=p, started_by=user, options={"push_railway_env": True})
    try:
        execute_pipeline(str(run.id))
    except Exception as exc:
        print(f"  Exception: {exc}")
    run.refresh_from_db()
    print(f"  Result: {run.status.upper()} {run.error_message[:100] if run.error_message else 'OK'}")
