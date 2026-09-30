"""import_studio_projects must carry runs and vault onto projects matched by slug."""

import sqlite3
import tempfile
import uuid
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.projects.models import Project
from apps.runs.models import PipelineRun, PipelineRunLog
from apps.vault.crypto import EncryptedPayload, decrypt_secret, encrypt_secret, generate_salt
from apps.vault.models import ProjectVault, VaultSecret

SOURCE_OWNER_ID = 7


def _build_source_db(path: Path, project_id: str, run_id: str, salt: bytes, payload) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE projects_project (id TEXT, name TEXT, slug TEXT, description TEXT, git_url TEXT,
            local_path TEXT, framework TEXT, language TEXT, scan_data TEXT, last_scanned_at TEXT, owner_id INT);
        CREATE TABLE runs_pipelinerun (id TEXT, project_id TEXT, status TEXT, options TEXT, result TEXT,
            error_message TEXT, readiness_score INT, created_at TEXT, started_at TEXT, completed_at TEXT);
        CREATE TABLE runs_pipelinerunlog (id INT, run_id TEXT, step TEXT, status TEXT, message TEXT,
            detail INT, score INT, created_at TEXT);
        CREATE TABLE vault_projectvault (project_id TEXT, salt BLOB);
        CREATE TABLE vault_vaultsecret (project_id TEXT, key_name TEXT, encrypted_value TEXT, iv TEXT,
            auth_tag TEXT, display_mask TEXT, key_mode TEXT, verified INT, verified_at TEXT,
            verification_message TEXT, created_at TEXT, updated_at TEXT);
        """
    )
    db.execute(
        "INSERT INTO projects_project VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (project_id, "EastBridge-OPS", "eastbridge-ops", "", "https://github.com/x/y.git",
         r"C:\Software Projects\EastBridge Ops Intelligence", "django", "python",
         '{"readiness": 91}', "2026-09-28 16:06:18", SOURCE_OWNER_ID),
    )
    db.execute(
        "INSERT INTO runs_pipelinerun VALUES (?,?,?,?,?,?,?,?,?,?)",
        (run_id, project_id, "completed", "{}", '{"ok": true}', "", 91,
         "2026-09-28 16:00:00", "2026-09-28 16:00:01", "2026-09-28 16:05:00"),
    )
    db.execute(
        "INSERT INTO runs_pipelinerunlog VALUES (?,?,?,?,?,?,?,?)",
        (1, run_id, "readiness", "ok", "score 91", 0, 91, "2026-09-28 16:04:00"),
    )
    db.execute("INSERT INTO vault_projectvault VALUES (?,?)", (project_id, salt))
    db.execute(
        "INSERT INTO vault_vaultsecret VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (project_id, "RAILWAY_API_TOKEN", payload.encrypted_value, payload.iv, payload.auth_tag,
         "rw_…abcd", "live", 1, None, "", "2026-09-28 16:00:00", "2026-09-28 16:00:00"),
    )
    db.commit()
    db.close()


class ImportIntoExistingProjectTests(TestCase):
    def test_runs_and_vault_follow_project_matched_by_slug(self):
        owner = get_user_model().objects.create_user(
            email="owner@example.com", password="x-long-test-password"
        )
        # Target already has the project (registered by hand) under a *different* UUID.
        existing = Project.objects.create(owner=owner, name="EastBridge-OPS", slug="eastbridge-ops")
        source_project_id = uuid.uuid4().hex
        self.assertNotEqual(existing.id.hex, source_project_id)
        run_id = uuid.uuid4().hex
        salt = generate_salt()
        payload = encrypt_secret("tok-123", salt)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.sqlite3"
            _build_source_db(source, source_project_id, run_id, salt, payload)
            with mock.patch(
                "apps.projects.management.commands.import_studio_projects.Command._backup_target"
            ):
                call_command(
                    "import_studio_projects",
                    source_db=source,
                    source_owner_id=SOURCE_OWNER_ID,
                    owner_email="owner@example.com",
                    include_runs=True,
                    include_vault=True,
                    apply=True,
                    stdout=StringIO(),
                )

        existing.refresh_from_db()
        self.assertEqual(Project.objects.filter(slug="eastbridge-ops").count(), 1)
        self.assertEqual(existing.scan_data, {"readiness": 91})

        run = PipelineRun.objects.get(pk=uuid.UUID(hex=run_id))
        self.assertEqual(run.project_id, existing.id)
        self.assertEqual(run.readiness_score, 91)
        self.assertEqual(PipelineRunLog.objects.filter(run=run).count(), 1)

        self.assertTrue(ProjectVault.objects.filter(project=existing).exists())
        secret = VaultSecret.objects.get(project=existing, key_name="RAILWAY_API_TOKEN")
        vault = ProjectVault.objects.get(project=existing)
        self.assertEqual(
            decrypt_secret(
                EncryptedPayload(secret.encrypted_value, secret.iv, secret.auth_tag), bytes(vault.salt)
            ),
            "tok-123",
        )

    def test_vault_refused_when_matched_target_already_has_secrets(self):
        owner = get_user_model().objects.create_user(
            email="owner2@example.com", password="x-long-test-password"
        )
        existing = Project.objects.create(owner=owner, name="EastBridge-OPS", slug="eastbridge-ops")
        VaultSecret.objects.create(project=existing, key_name="X", encrypted_value="a", iv="b", auth_tag="c")
        salt = generate_salt()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.sqlite3"
            _build_source_db(source, uuid.uuid4().hex, uuid.uuid4().hex, salt, encrypt_secret("t", salt))
            with self.assertRaisesMessage(Exception, "target projects already contain secrets"):
                call_command(
                    "import_studio_projects",
                    source_db=source,
                    source_owner_id=SOURCE_OWNER_ID,
                    owner_email="owner2@example.com",
                    include_vault=True,
                    apply=True,
                    stdout=StringIO(),
                )


class SkipUnreadableVaultTests(TestCase):
    def test_unreadable_secret_is_skipped_and_readable_one_imported(self):
        owner = get_user_model().objects.create_user(email="owner3@example.com", password="x-long-test-password")
        salt = generate_salt()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.sqlite3"
            project_id = uuid.uuid4().hex
            _build_source_db(source, project_id, uuid.uuid4().hex, salt, encrypt_secret("good", salt))
            db = sqlite3.connect(source)
            bad = encrypt_secret("old", salt, master_key=b"k" * 32)  # encrypted with a different key
            db.execute(
                "INSERT INTO vault_vaultsecret VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, "OLD_TOKEN", bad.encrypted_value, bad.iv, bad.auth_tag, "", "live", 0, None, "",
                 "2026-09-28 16:00:00", "2026-09-28 16:00:00"),
            )
            db.commit()
            db.close()
            common = dict(source_db=source, source_owner_id=SOURCE_OWNER_ID, owner_email="owner3@example.com",
                          include_vault=True, apply=True, stdout=StringIO())
            with mock.patch("apps.projects.management.commands.import_studio_projects.Command._backup_target"):
                with self.assertRaisesMessage(Exception, "unreadable"):
                    call_command("import_studio_projects", **common)
                call_command("import_studio_projects", skip_unreadable_vault=True, **common)
        keys = set(VaultSecret.objects.filter(project__slug="eastbridge-ops").values_list("key_name", flat=True))
        self.assertEqual(keys, {"RAILWAY_API_TOKEN"})
