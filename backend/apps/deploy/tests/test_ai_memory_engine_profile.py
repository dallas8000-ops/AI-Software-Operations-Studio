from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.deploy.env_push import ENV_PRESETS
from apps.deploy.platform import framework_build_command, framework_start_command, health_check_path
from apps.deploy.railway_resolve import preset_for_project
from apps.projects.scanner import ProjectScanner


class AiMemoryEngineProfileTests(SimpleTestCase):
    def test_fastapi_project_uses_railway_profile(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "server.py").write_text(
                "from fastapi import FastAPI\napp = FastAPI()\n",
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")

            scan = ProjectScanner(root).scan()

        self.assertEqual(scan.framework, "fastapi")
        self.assertEqual(scan.language, "python")
        self.assertEqual(framework_build_command("fastapi"), "pip install -r requirements.txt")
        self.assertEqual(
            framework_start_command("fastapi"),
            "uvicorn server:app --host 0.0.0.0 --port $PORT",
        )
        self.assertEqual(health_check_path("fastapi"), "/health")
        self.assertEqual(ENV_PRESETS["ai-memory-engine"]["MEMORY_DATA_PATH"], "/data/memories")

    def test_ai_memory_engine_resolves_its_own_preset(self):
        class ProjectStub:
            slug = "ai-memory-engine"

        self.assertEqual(preset_for_project(ProjectStub()), "ai-memory-engine")