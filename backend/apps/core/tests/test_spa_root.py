import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class StudioRootTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dist = Path(self.temp_dir.name)
        (self.dist / "index.html").write_text(
            "<!doctype html><title>Operations Studio test shell</title>",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_root_serves_spa_and_api_metadata_has_its_own_route(self):
        with override_settings(FRONTEND_DIST=self.dist):
            root_response = self.client.get("/")
            api_response = self.client.get("/api/")

        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(root_response["Content-Type"], "text/html")
        self.assertIn(b"Operations Studio test shell", b"".join(root_response.streaming_content))
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["service"], "AI Software Operations Studio API")
