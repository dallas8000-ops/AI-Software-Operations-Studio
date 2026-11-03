"""Regression tests for the vault hardening that never reached main (found 2026-11-03).

Each test fails on the pre-fix code:
- a Railway container with no VAULT_MASTER_KEY used to silently generate a throwaway key;
- a crash halfway through key rotation used to leave secrets under two different keys;
- the vault UI used to hand out STRIPE_WEBHOOK_SECRET in plaintext;
- production used to boot with the public placeholder DJANGO_SECRET_KEY.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.models import User
from apps.projects.models import Project
from apps.vault import rotation
from apps.vault.crypto import EncryptedPayload, decrypt_secret, encrypt_secret, generate_salt
from apps.vault.master_key import _resolve_for_railway
from apps.vault.models import ProjectVault, VaultSecret
from apps.vault.views_copy import COPYABLE_VAULT_KEYS

OLD = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
NEW = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
OLD_BYTES, NEW_BYTES = bytes.fromhex(OLD), bytes.fromhex(NEW)
BACKEND_DIR = Path(__file__).resolve().parents[3]


class RailwayMasterKeyTests(SimpleTestCase):
    def test_refuses_to_generate_a_throwaway_key_on_railway(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _resolve_for_railway(Path(tmp) / "vault-master-key", env_key="", file_key="")
        self.assertIn("VAULT_MASTER_KEY", str(ctx.exception))

    def test_env_key_still_used_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = _resolve_for_railway(Path(tmp) / "vault-master-key", env_key=OLD, file_key="")
        self.assertEqual(key, OLD)


@override_settings(VAULT_MASTER_KEY=OLD)
class RotationAtomicityTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="rot@t.com", password="pass12345")
        self.project = Project.objects.create(name="Rot", slug="rot", owner=user)
        self.salt = generate_salt()
        ProjectVault.objects.create(project=self.project, salt=self.salt)
        for name, value in (("KEY_A", "alpha"), ("KEY_B", "bravo")):
            p = encrypt_secret(value, self.salt, master_key=OLD_BYTES)
            VaultSecret.objects.create(
                project=self.project,
                key_name=name,
                encrypted_value=p.encrypted_value,
                iv=p.iv,
                auth_tag=p.auth_tag,
            )

    def _decrypt_all_with(self, key):
        out = {}
        for s in VaultSecret.objects.filter(project=self.project):
            payload = EncryptedPayload(encrypted_value=s.encrypted_value, iv=s.iv, auth_tag=s.auth_tag)
            out[s.key_name] = decrypt_secret(payload, bytes(self.salt), master_key=key)
        return out

    def test_crash_mid_rotation_leaves_every_secret_on_the_old_key(self):
        real_encrypt = rotation.encrypt_secret
        calls = {"n": 0}

        def encrypt_then_crash(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated crash mid-rotation")
            return real_encrypt(*args, **kwargs)

        with patch.object(rotation, "encrypt_secret", side_effect=encrypt_then_crash):
            with self.assertRaises(RuntimeError):
                rotation.rotate_vault_master_key(NEW)

        # Both secrets must still open with the OLD key; none may be stranded on NEW.
        self.assertEqual(self._decrypt_all_with(OLD_BYTES), {"KEY_A": "alpha", "KEY_B": "bravo"})

    def test_successful_rotation_moves_every_secret(self):
        result = rotation.rotate_vault_master_key(NEW)
        self.assertEqual(result.secrets, 2)
        self.assertEqual(self._decrypt_all_with(NEW_BYTES), {"KEY_A": "alpha", "KEY_B": "bravo"})


class VaultCopyAllowlistTests(SimpleTestCase):
    def test_webhook_signing_secret_is_never_copyable(self):
        self.assertNotIn("STRIPE_WEBHOOK_SECRET", COPYABLE_VAULT_KEYS)
        self.assertTrue(all("SECRET" not in k for k in COPYABLE_VAULT_KEYS))


class ProductionSecretKeyGuardTests(SimpleTestCase):
    def _import_settings(self, secret_key):
        env = {k: v for k, v in os.environ.items() if not k.startswith("RAILWAY_")}
        env.update(
            RAILWAY_ENVIRONMENT="production",
            DJANGO_SECRET_KEY=secret_key,
            DJANGO_DEBUG="false",
            # Never connected to: importing settings only validates the URL shape.
            DATABASE_URL="postgresql://u:p@localhost:5432/studio_settings_test",
        )
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_railway_refuses_placeholder_secret_key(self):
        proc = self._import_settings("dev-only-change-me-in-production")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY is not set on Railway", proc.stderr)

    def test_railway_boots_with_a_real_secret_key(self):
        proc = self._import_settings("x" * 50)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
