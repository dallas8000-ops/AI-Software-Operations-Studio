"""Cloud setup — verify an already-deployed app when the Studio has no local project folder.

Used on the hosted Studio (Railway container), where ``C:\\...`` app folders do not exist.
Read-only against Railway and Stripe: copies existing Railway variables into the vault
(never overwriting vault values), checks health and webhook registration, and records a
completed PipelineRun with readiness checks. Verification never pushes env, rotates webhook secrets,
creates domains, or writes files; ``register_webhook`` is the one explicit, confirmed repair.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from django.utils import timezone

from apps.projects.models import Project
from apps.runs.models import PipelineRun
from apps.stripe_core.portfolio_catalog import PORTFOLIO_CATALOG, CatalogEntry, is_stripe_exempt_slug
from apps.vault.import_env import is_importable_key
from apps.vault.models import get_secret, set_secret

HEALTH_TIMEOUT_SECONDS = 10


def needs_cloud_setup(project: Project) -> bool:
    """Readiness always comes from Railway and the live URL, never from a local folder."""
    return True


def catalog_entry_for(project: Project) -> CatalogEntry | None:
    """Catalog entry by slug, then by name — hand-added projects may have suffixed slugs."""
    name = project.name.strip().casefold()
    for entry in PORTFOLIO_CATALOG:
        if entry.get("merged"):
            continue
        if entry.get("projectSlug") == project.slug:
            return entry
    for entry in PORTFOLIO_CATALOG:
        if entry.get("merged"):
            continue
        if name and str(entry.get("name") or "").strip().casefold() == name:
            return entry
    return None


def _railway_token(project: Project) -> str:
    # The Studio's own service variable wins: vault copies on other projects can be stale.
    token = (os.environ.get("RAILWAY_API_TOKEN") or "").strip()
    if token:
        return token
    token = (get_secret(project, "RAILWAY_API_TOKEN") or "").strip()
    if token:
        return token
    for other in Project.objects.filter(owner=project.owner).exclude(pk=project.pk):
        token = (get_secret(other, "RAILWAY_API_TOKEN") or "").strip()
        if token:
            return token
    return ""


def _check(check_id: str, name: str, status: str, message: str, fix: str | None = None) -> dict[str, Any]:
    return {"id": check_id, "name": name, "status": status, "message": message, "fix": fix}


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def _join(base: str, path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    return f"{base.rstrip('/')}{path}"


def _find_railway_service(token: str, entry: CatalogEntry) -> tuple[str | None, str | None, str]:
    from .railway_resolve import resolve_railway_service_by_host

    for key in ("productionUrl", "webProductionUrl"):
        host = _host(str(entry.get(key) or ""))
        if not host:
            continue
        project_id, service_id = resolve_railway_service_by_host(token, host)
        if project_id and service_id:
            return project_id, service_id, host
    return None, None, _host(str(entry.get("productionUrl") or ""))


def _import_railway_vars(project: Project, variables: dict[str, str]) -> list[str]:
    """Copy importable Railway variables into the vault; never overwrite existing vault values."""
    from .env_push import is_placeholder_database_url

    imported: list[str] = []
    for key, value in variables.items():
        value = str(value or "").strip()
        if not value or not is_importable_key(key):
            continue
        if key == "DATABASE_URL" and is_placeholder_database_url(value):
            continue
        if get_secret(project, key):
            continue
        set_secret(project, key, value)
        imported.append(key)
    return sorted(imported)


def _health_check(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "OperationsStudio-CloudSetup/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{url} unreachable ({exc})"
    return 200 <= code < 400, f"{url} returned HTTP {code}"


def _webhook_check(secret_key: str, webhook_url: str) -> tuple[str, str]:
    import stripe

    try:
        endpoints = stripe.WebhookEndpoint.list(limit=100, api_key=secret_key).data
    except stripe.StripeError as exc:
        return "fail", f"Could not list Stripe webhooks: {exc.user_message or exc}"
    target = webhook_url.rstrip("/")
    match = next((e for e in endpoints if (e.url or "").rstrip("/") == target), None)
    if not match:
        return "fail", f"No Stripe webhook registered for {webhook_url}"
    if getattr(match, "status", "enabled") != "enabled":
        return "warn", f"Stripe webhook for {webhook_url} is {match.status}"
    return "pass", f"Stripe webhook registered and enabled for {webhook_url}"


def _score(checks: list[dict[str, Any]]) -> int:
    if not checks:
        return 0
    points = sum(1.0 if c["status"] == "pass" else 0.5 if c["status"] == "warn" else 0.0 for c in checks)
    return round(100 * points / len(checks))


def verify_project(project: Project) -> dict[str, Any]:
    """Run cloud checks; returns {checks, imported, railway}."""
    checks: list[dict[str, Any]] = []
    imported: list[str] = []
    railway: dict[str, Any] = {}

    entry = catalog_entry_for(project)
    if not entry:
        checks.append(
            _check(
                "catalog",
                "Portfolio catalog",
                "fail",
                f"{project.name} is not in the portfolio catalog, so its Railway service and URLs are unknown",
                "Add it to PORTFOLIO_CATALOG or archive this duplicate project",
            )
        )
        return {"checks": checks, "imported": imported, "railway": railway}

    base_url = str(entry.get("productionUrl") or "").rstrip("/")
    token = _railway_token(project)
    variables: dict[str, str] = {}
    if not token:
        checks.append(
            _check(
                "railway_token",
                "Railway access",
                "fail",
                "No Railway API token available to the Studio",
                "Add RAILWAY_API_TOKEN to the operations-studio-web Railway variables",
            )
        )
    else:
        project_id, service_id, host = _find_railway_service(token, entry)
        if not service_id:
            checks.append(
                _check(
                    "railway_service",
                    "Railway service",
                    "fail",
                    f"No Railway service serves {host or 'the catalog URL'}",
                    "Update productionUrl in the portfolio catalog to the service's live domain",
                )
            )
        else:
            from .env_push import _railway_environment_id, get_railway_env_vars

            try:
                environment_id = _railway_environment_id(token, project_id)
                variables = get_railway_env_vars(token, project_id, service_id, environment_id)
            except Exception as exc:  # one app's Railway error must not fail the whole run
                checks.append(
                    _check(
                        "railway_service",
                        "Railway service",
                        "fail",
                        f"Found the service for {host} but could not read its variables: {exc}",
                        "Check the RAILWAY_API_TOKEN has access to this service's project",
                    )
                )
            else:
                railway = {"projectId": project_id, "serviceId": service_id, "environmentId": environment_id}
                imported = _import_railway_vars(project, variables)
                checks.append(
                    _check(
                        "railway_service",
                        "Railway service",
                        "pass",
                        f"Found Railway service for {host}; {len(imported)} key(s) copied into the vault",
                    )
                )

    def value(key: str) -> str:
        # The app's Railway variables are the truth once read; the vault is only a fallback
        # when Railway was unreachable (it can hold hub or env-file values for other apps).
        if railway:
            return str(variables.get(key) or "").strip()
        return (get_secret(project, key) or "").strip()

    if not is_stripe_exempt_slug(entry.get("projectSlug") or ""):
        secret_key = value("STRIPE_SECRET_KEY")
        has_publishable = bool(value("STRIPE_PUBLISHABLE_KEY") or value("NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY"))
        checks.append(
            _check(
                "stripe_keys",
                "Stripe keys",
                "pass" if secret_key and has_publishable else "fail",
                "Stripe secret and publishable keys are set"
                if secret_key and has_publishable
                else "Stripe secret or publishable key missing from the app's Railway variables",
                None if secret_key and has_publishable else "Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY on the app's Railway service",
            )
        )
        has_whsec = bool(value("STRIPE_WEBHOOK_SECRET"))
        checks.append(
            _check(
                "webhook_secret",
                "Webhook signing secret",
                "pass" if has_whsec else "fail",
                "STRIPE_WEBHOOK_SECRET is set" if has_whsec else "STRIPE_WEBHOOK_SECRET missing from the app's Railway variables",
            )
        )
        webhook_path = str(entry.get("webhookPath") or "").strip()
        if secret_key and base_url and webhook_path:
            status_value, message = _webhook_check(secret_key, _join(base_url, webhook_path))
            checks.append(_check("stripe_webhook", "Stripe webhook", status_value, message))

    db_url = value("DATABASE_URL")
    if not db_url:
        db_status, db_msg = "warn", "DATABASE_URL not set on the app's Railway service"
    elif not re.match(r"^(postgres(ql)?|mysql|mariadb|redis|mongodb(\+srv)?)://", db_url, re.I):
        db_status, db_msg = "fail", "DATABASE_URL is malformed (does not start with a valid scheme such as postgresql://)"
    else:
        db_status, db_msg = "pass", "DATABASE_URL is set"
    checks.append(_check("database", "Database", db_status, db_msg))

    if base_url:
        ok, message = _health_check(_join(base_url, str(entry.get("healthPath") or "/")))
        checks.append(_check("health", "Live health check", "pass" if ok else "fail", message))

    return {"checks": checks, "imported": imported, "railway": railway}


def register_webhook(project: Project) -> dict[str, Any]:
    """Register the catalog webhook in Stripe and push the signing secret to the Railway service."""
    import stripe

    from apps.stripe_core.provision import DEFAULT_WEBHOOK_EVENTS, _register_webhook

    from .env_push import auto_push_railway_env

    entry = catalog_entry_for(project)
    if not entry:
        raise ValueError(f"{project.name} is not in the portfolio catalog")
    base_url = str(entry.get("productionUrl") or "").rstrip("/")
    webhook_path = str(entry.get("webhookPath") or "").strip()
    if not (base_url and webhook_path):
        raise ValueError("Catalog entry has no productionUrl/webhookPath")
    secret_key = (get_secret(project, "STRIPE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise ValueError("STRIPE_SECRET_KEY is not in the project vault")

    webhook_url = _join(base_url, webhook_path)
    stripe.api_key = secret_key
    try:
        webhook = _register_webhook(webhook_url, list(DEFAULT_WEBHOOK_EVENTS))
    finally:
        stripe.api_key = None
    result: dict[str, Any] = {"webhookUrl": webhook_url, "endpointId": webhook["id"], "reused": webhook["reused"]}
    secret = webhook.get("secret")
    if not secret:
        result["warning"] = "Stripe returned no signing secret; Railway was not updated."
        return result
    set_secret(project, "STRIPE_WEBHOOK_SECRET", secret)
    push = auto_push_railway_env(project, variables={"STRIPE_WEBHOOK_SECRET": secret})
    result["pushed"] = push.get("pushed", [])
    result["message"] = push.get("message", "")
    return result


def run_cloud_setup(project: Project, *, user=None) -> PipelineRun:
    """Verify the project and record the result as a completed pipeline run."""
    started = timezone.now()
    try:
        outcome = verify_project(project)
        error = ""
    except Exception as exc:  # recorded on the run instead of a 500
        outcome = {"checks": [], "imported": [], "railway": {}}
        error = str(exc)[:500]
    score = _score(outcome["checks"])
    return PipelineRun.objects.create(
        project=project,
        started_by=user,
        status=PipelineRun.Status.FAILED if error else PipelineRun.Status.COMPLETED,
        options={"mode": "cloud_setup"},
        result={
            "mode": "cloud_setup",
            "readiness": {"score": score, "checks": outcome["checks"]},
            "importedKeys": outcome["imported"],
            "railway": outcome["railway"],
        },
        error_message=error,
        readiness_score=None if error else score,
        started_at=started,
        completed_at=timezone.now(),
    )
