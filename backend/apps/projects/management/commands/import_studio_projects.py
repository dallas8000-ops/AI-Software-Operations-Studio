"""Import project metadata into Studio without copying secrets or run history."""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_datetime

from apps.projects.models import Project
from apps.quality.models import QualityProjectLink
from apps.runs.models import PipelineRun, PipelineRunLog
from apps.vault.crypto import EncryptedPayload, decrypt_secret
from apps.vault.models import ProjectVault, VaultSecret

EXCLUDED_PREFIXES = ("burn-", "smoke-")
SPECWRIGHT_SLUGS = {
    "dbops-control-center": "DBOps-Control-Center",
    "elite-fintech-systems": "Elite Fintech Systems",
}
SLUG_ALIASES = {
    "httpsgithubcomdallas8000-opseastbridge-ops": "eastbridge-ops",
}


def _connect_read_only(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


class Command(BaseCommand):
    help = "Dry-run or import safe project metadata from Deployment Center and Specwright SQLite databases."

    def add_arguments(self, parser):
        parser.add_argument("--source-db", required=True, type=Path)
        parser.add_argument("--specwright-db", type=Path)
        parser.add_argument("--source-owner-id", type=int, default=4)
        parser.add_argument("--owner-email", default="studio-review@example.local")
        parser.add_argument("--include-runs", action="store_true")
        parser.add_argument("--audit-vault", action="store_true")
        parser.add_argument("--include-vault", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        source_path: Path = options["source_db"]
        specwright_path: Path | None = options.get("specwright_db")
        source_owner_id = options["source_owner_id"]
        apply = options["apply"]

        if not source_path.is_file():
            raise CommandError(f"Source database not found: {source_path}")
        source = _connect_read_only(source_path)
        try:
            rows = list(
                source.execute(
                    """
                    SELECT id, name, slug, description, git_url, local_path, framework, language,
                           scan_data, last_scanned_at
                    FROM projects_project WHERE owner_id = ? ORDER BY slug
                    """,
                    (source_owner_id,),
                )
            )
        finally:
            source.close()

        rows = [row for row in rows if not row["slug"].startswith(EXCLUDED_PREFIXES)]
        self.stdout.write(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
        self.stdout.write(f"Source projects selected: {len(rows)}")
        for row in rows:
            self.stdout.write(f"  {row['slug']}: {row['name']}")

        run_rows, log_rows = self._run_history(source_path, {row["id"] for row in rows}) if options["include_runs"] else ([], [])
        if options["include_runs"]:
            self.stdout.write(f"Pipeline history selected: {len(run_rows)} runs, {len(log_rows)} logs")
        vault_audit = None
        if options["audit_vault"] or options["include_vault"]:
            vault_audit = self._vault_audit(source_path, {row["id"] for row in rows})
            self.stdout.write(f"Vault compatibility: {vault_audit['readable']}/{vault_audit['total']} encrypted records readable")
            for project_slug, keys in vault_audit["unreadable"].items():
                self.stdout.write(self.style.ERROR(f"  unreadable {project_slug}: {', '.join(keys)}"))
        vault_rows, secret_rows = self._vault_records(source_path, {row["id"] for row in rows}) if options["include_vault"] else ([], [])
        if options["include_vault"]:
            self.stdout.write(f"Encrypted vault data selected: {len(vault_rows)} vaults, {len(secret_rows)} secrets")
            if vault_audit and vault_audit["readable"] != vault_audit["total"]:
                raise CommandError("Vault import refused because one or more source records are unreadable.")

        specwright_matches = self._specwright_matches(specwright_path)
        for slug, project_id in specwright_matches.items():
            self.stdout.write(f"  quality link: {slug} -> Specwright {project_id}")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry run only; no target data changed. Add --apply after review."))
            return

        owner = get_user_model().objects.filter(email__iexact=options["owner_email"]).first()
        if not owner:
            raise CommandError(f"Target owner not found: {options['owner_email']}")
        selected_project_ids = [uuid.UUID(hex=row["id"]) for row in rows]
        if options["include_vault"] and VaultSecret.objects.filter(project_id__in=selected_project_ids).exists():
            raise CommandError("Vault import refused: target projects already contain secrets. No records were changed.")
        self._backup_target()

        created = updated = 0
        with transaction.atomic():
            imported: dict[str, Project] = {}
            for row in rows:
                slug = SLUG_ALIASES.get(row["slug"], row["slug"])
                defaults = {
                    "name": row["name"],
                    "description": row["description"] or "",
                    "git_url": row["git_url"] or "",
                    "local_path": row["local_path"] or "",
                    "framework": row["framework"] or "unknown",
                    "language": row["language"] or "unknown",
                    "scan_data": self._json_value(row["scan_data"]),
                    "last_scanned_at": self._datetime_value(row["last_scanned_at"]),
                }
                if slug == "eastbridge-ops" and not defaults["local_path"]:
                    defaults["local_path"] = r"C:\Software Projects\EastBridge Ops Intelligence"
                project = Project.objects.filter(owner=owner, slug=slug).first()
                if project:
                    for field, value in defaults.items():
                        setattr(project, field, value)
                    project.save()
                    updated += 1
                else:
                    project = Project.objects.create(
                        id=uuid.UUID(hex=row["id"]), owner=owner, slug=slug, **defaults
                    )
                    created += 1
                imported[slug] = project

            for slug, specwright_id in specwright_matches.items():
                project = imported.get(slug)
                if not project:
                    continue
                existing = QualityProjectLink.objects.filter(specwright_project_id=specwright_id).first()
                if existing and existing.project.slug == "specwright-review":
                    existing.project = project
                    existing.specwright_project_name = SPECWRIGHT_SLUGS[slug]
                    existing.save(update_fields=["project", "specwright_project_name", "updated_at"])
                elif not existing:
                    QualityProjectLink.objects.update_or_create(
                        project=project,
                        defaults={"specwright_project_id": specwright_id, "specwright_project_name": SPECWRIGHT_SLUGS[slug]},
                    )

            runs_created = runs_updated = 0
            for row in run_rows:
                project = Project.objects.filter(pk=uuid.UUID(hex=row["project_id"]), owner=owner).first()
                if not project:
                    continue
                run_id = uuid.UUID(hex=row["id"])
                _, was_created = PipelineRun.objects.update_or_create(
                    id=run_id,
                    defaults={
                        "project": project,
                        "started_by": owner,
                        "status": row["status"],
                        "options": self._json_value(row["options"]),
                        "result": self._json_value(row["result"]),
                        "error_message": row["error_message"] or "",
                        "readiness_score": row["readiness_score"],
                        "started_at": self._datetime_value(row["started_at"]),
                        "completed_at": self._datetime_value(row["completed_at"]),
                    },
                )
                PipelineRun.objects.filter(pk=run_id).update(created_at=self._datetime_value(row["created_at"]))
                runs_created += int(was_created)
                runs_updated += int(not was_created)

            logs_created = logs_updated = 0
            for row in log_rows:
                run_id = uuid.UUID(hex=row["run_id"])
                if not PipelineRun.objects.filter(pk=run_id).exists():
                    continue
                _, was_created = PipelineRunLog.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "run_id": run_id,
                        "step": row["step"],
                        "status": row["status"],
                        "message": row["message"],
                        "detail": bool(row["detail"]),
                        "score": row["score"],
                    },
                )
                PipelineRunLog.objects.filter(pk=row["id"]).update(created_at=self._datetime_value(row["created_at"]))
                logs_created += int(was_created)
                logs_updated += int(not was_created)

            vaults_imported = secrets_imported = 0
            for row in vault_rows:
                project = Project.objects.filter(pk=uuid.UUID(hex=row["project_id"]), owner=owner).first()
                if not project:
                    continue
                ProjectVault.objects.update_or_create(project=project, defaults={"salt": bytes(row["salt"])})
                vaults_imported += 1
            for row in secret_rows:
                project = Project.objects.filter(pk=uuid.UUID(hex=row["project_id"]), owner=owner).first()
                if not project:
                    continue
                secret, _ = VaultSecret.objects.update_or_create(
                    project=project,
                    key_name=row["key_name"],
                    defaults={
                        "encrypted_value": row["encrypted_value"],
                        "iv": row["iv"],
                        "auth_tag": row["auth_tag"],
                        "display_mask": row["display_mask"] or "",
                        "key_mode": row["key_mode"] or "unknown",
                        "verified": bool(row["verified"]),
                        "verified_at": self._datetime_value(row["verified_at"]),
                        "verification_message": row["verification_message"] or "",
                    },
                )
                VaultSecret.objects.filter(pk=secret.pk).update(
                    created_at=self._datetime_value(row["created_at"]),
                    updated_at=self._datetime_value(row["updated_at"]),
                )
                secrets_imported += 1

        self.stdout.write(self.style.SUCCESS(f"Project metadata imported: {created} created, {updated} updated."))
        if options["include_runs"]:
            self.stdout.write(self.style.SUCCESS(f"Pipeline history imported: {runs_created} runs created, {runs_updated} updated; {logs_created} logs created, {logs_updated} updated."))
            self.stdout.write("Secrets, users, organizations, and subscriptions were not copied.")
        elif options["include_vault"]:
            self.stdout.write("Users, organizations, subscriptions, pipeline runs, and logs were not copied.")
        else:
            self.stdout.write("Secrets, users, organizations, subscriptions, pipeline runs, and logs were not copied.")
        if options["include_vault"]:
            self.stdout.write(self.style.SUCCESS(f"Encrypted vault data imported: {vaults_imported} vaults, {secrets_imported} secrets."))

    def _backup_target(self) -> None:
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Automatic apply is currently limited to a SQLite Studio target.")
        source = Path(db["NAME"])
        backup_dir = source.parent / ".migration-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(datetime_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = backup_dir / f"studio-before-project-import-{stamp}.sqlite3"
        connection.close()
        shutil.copy2(source, destination)
        self.stdout.write(f"Target backup: {destination}")

    @staticmethod
    def _json_value(raw):
        import json

        if not raw:
            return {}
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _datetime_value(raw):
        if not raw:
            return None
        value = parse_datetime(raw) if isinstance(raw, str) else raw
        if value and django_timezone.is_naive(value):
            return django_timezone.make_aware(value, datetime_timezone.utc)
        return value

    @staticmethod
    def _specwright_matches(path: Path | None) -> dict[str, int]:
        if not path or not path.is_file():
            return {}
        db = _connect_read_only(path)
        try:
            projects = list(db.execute("SELECT id, name FROM projects"))
        finally:
            db.close()
        by_name = {row["name"].casefold(): row["id"] for row in projects}
        return {
            slug: by_name[name.casefold()]
            for slug, name in SPECWRIGHT_SLUGS.items()
            if name.casefold() in by_name
        }

    @staticmethod
    def _run_history(path: Path, project_ids: set[str]) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
        if not project_ids:
            return [], []
        db = _connect_read_only(path)
        try:
            placeholders = ",".join("?" for _ in project_ids)
            runs = list(
                db.execute(
                    f"""SELECT id, project_id, status, options, result, error_message, readiness_score,
                                created_at, started_at, completed_at
                         FROM runs_pipelinerun WHERE project_id IN ({placeholders})""",
                    tuple(project_ids),
                )
            )
            run_ids = [row["id"] for row in runs]
            if not run_ids:
                return runs, []
            run_placeholders = ",".join("?" for _ in run_ids)
            logs = list(
                db.execute(
                    f"""SELECT id, run_id, step, status, message, detail, score, created_at
                         FROM runs_pipelinerunlog WHERE run_id IN ({run_placeholders}) ORDER BY id""",
                    tuple(run_ids),
                )
            )
            return runs, logs
        finally:
            db.close()

    @staticmethod
    def _vault_audit(path: Path, project_ids: set[str]) -> dict:
        if not project_ids:
            return {"total": 0, "readable": 0, "unreadable": {}}
        db = _connect_read_only(path)
        try:
            placeholders = ",".join("?" for _ in project_ids)
            rows = list(
                db.execute(
                    f"""SELECT p.slug, v.salt, s.key_name, s.encrypted_value, s.iv, s.auth_tag
                         FROM projects_project p
                         JOIN vault_projectvault v ON v.project_id = p.id
                         JOIN vault_vaultsecret s ON s.project_id = p.id
                         WHERE p.id IN ({placeholders}) ORDER BY p.slug, s.key_name""",
                    tuple(project_ids),
                )
            )
        finally:
            db.close()
        readable = 0
        unreadable: dict[str, list[str]] = {}
        for row in rows:
            try:
                decrypt_secret(
                    EncryptedPayload(row["encrypted_value"], row["iv"], row["auth_tag"]),
                    bytes(row["salt"]),
                )
                readable += 1
            except Exception:
                unreadable.setdefault(row["slug"], []).append(row["key_name"])
        return {"total": len(rows), "readable": readable, "unreadable": unreadable}

    @staticmethod
    def _vault_records(path: Path, project_ids: set[str]) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
        if not project_ids:
            return [], []
        db = _connect_read_only(path)
        try:
            placeholders = ",".join("?" for _ in project_ids)
            vaults = list(
                db.execute(
                    f"SELECT project_id, salt FROM vault_projectvault WHERE project_id IN ({placeholders})",
                    tuple(project_ids),
                )
            )
            secrets = list(
                db.execute(
                    f"""SELECT project_id, key_name, encrypted_value, iv, auth_tag, display_mask,
                                key_mode, verified, verified_at, verification_message, created_at, updated_at
                         FROM vault_vaultsecret WHERE project_id IN ({placeholders}) ORDER BY project_id, key_name""",
                    tuple(project_ids),
                )
            )
            return vaults, secrets
        finally:
            db.close()
