"""Cloud setup — verify an already-deployed app when the Studio has no local project folder.

Used on the hosted Studio (Railway container), where ``C:\\...`` app folders do not exist.
Read-only against Railway and Stripe: copies existing Railway variables into the vault
(never overwriting vault values), checks health and webhook registration, and records a
completed PipelineRun with readiness checks. After verifying, ``_auto_repair`` fixes failed checks with the Studio's own push and webhook features.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from django.utils import timezone

from apps.projects.models import Project
from apps.runs.models import PipelineRun
from apps.stripe_core.portfolio_catalog import (
    DATABASE_OPTIONAL_SLUGS,
    PORTFOLIO_CATALOG,
    CatalogEntry,
    is_stripe_exempt_slug,
)
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


def _database_setting(value, variables: dict[str, str]) -> tuple[str, str]:
    """DATABASE_URL, or an app-prefixed one such as SPECWRIGHT_DATABASE_URL."""
    direct = value("DATABASE_URL")
    if direct:
        return "DATABASE_URL", direct
    for key in sorted(variables):
        if key.endswith("_DATABASE_URL") and str(variables.get(key) or "").strip():
            return key, str(variables[key]).strip()
    return "DATABASE_URL", ""


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
            body = response.read(4000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        body = ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{url} unreachable ({exc})"
    if not 200 <= code < 400:
        return False, f"{url} returned HTTP {code}"
    path = urlparse(url).path
    if path not in ("", "/") and (body.lstrip("\ufeff \r\n\t").lower().startswith(("<!doctype", "<html"))):
        return False, f"{url} returned a web page, not a health response (no API health endpoint is serving this path)"
    reported = _reported_unhealthy(body)
    if reported:
        return False, f"{url} returned HTTP {code} but reports: {reported}"
    return True, f"{url} returned HTTP {code}"


def _reported_unhealthy(body: str) -> str:
    """Return what a JSON health body says is wrong, or "" when it is healthy or not JSON."""
    try:
        data = json.loads(body)
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    if data.get("ok") is False:
        return "ok=false"
    for db_key in ("db", "database"):
        if data.get(db_key) is False:
            return f"{db_key}=false"
    status = str(data.get("status", "")).strip().lower()
    if status in {"error", "unhealthy", "down", "fail", "failed", "degraded"}:
        return f"status={status}"
    for key, val in data.items():
        if key != "status" and isinstance(val, str) and val.strip().lower() in {"error", "down", "unhealthy", "fail", "failed", "unreachable", "disconnected"}:
            return f"{key}={val.strip().lower()}"
    return ""


def _signed_webhook_check(url: str, whsec: str) -> tuple[str, str]:
    """Send a signed test event to the app's webhook with the secret held on Railway."""
    from apps.stripe_core.webhook_delivery import probe_signed_webhook

    if not whsec.startswith("whsec_"):
        return "fail", "STRIPE_WEBHOOK_SECRET on Railway is not a valid whsec_ signing secret"
    probe = probe_signed_webhook(None, url=url, whsec=whsec)
    if probe is None:
        return "warn", "Could not run the signed webhook test"
    kind = probe.classification
    if kind == "ok":
        return "pass", f"App accepted a signed test event at {probe.url} (HTTP {probe.httpStatus})"
    if kind == "signature_mismatch":
        return "fail", f"App rejected the signing secret held on Railway at {probe.url} (HTTP {probe.httpStatus})"
    if kind == "route_missing":
        return "fail", f"No webhook route at {probe.url} (HTTP 404)"
    if kind == "handler_error":
        return "fail", f"Webhook handler crashed at {probe.url} (HTTP 500)"
    if kind == "unreachable":
        return "warn", f"Could not reach {probe.url}"
    return "warn", f"Webhook test at {probe.url} was inconclusive ({kind}, HTTP {probe.httpStatus})"


def _stripe_key_check(secret_key: str) -> tuple[str, str]:
    """Ask Stripe whether the app's secret key is actually valid."""
    import stripe

    try:
        stripe.Balance.retrieve(api_key=secret_key)
    except stripe.AuthenticationError:
        return "fail", "Stripe rejected the app's STRIPE_SECRET_KEY (invalid, revoked or expired)"
    except stripe.PermissionError:
        return "pass", "Stripe accepted the key (restricted key without balance access)"
    except stripe.StripeError as exc:
        return "warn", f"Could not verify the Stripe key: {exc.user_message or exc}"
    return "pass", "Stripe accepted the app's secret key"


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
                for attempt_no in range(3):  # Railway intermittently answers "Not Authorized" under load
                    try:
                        environment_id = _railway_environment_id(token, project_id)
                        variables = get_railway_env_vars(token, project_id, service_id, environment_id)
                        break
                    except Exception:
                        if attempt_no == 2:
                            raise
                        time.sleep(1.5 * (attempt_no + 1))
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
        if secret_key:
            key_status, key_message = _stripe_key_check(secret_key)
            checks.append(_check("stripe_key_valid", "Stripe key accepted by Stripe", key_status, key_message))
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
            if status_value == "pass" and has_whsec:
                sig_status, sig_message = _signed_webhook_check(_join(base_url, webhook_path), value("STRIPE_WEBHOOK_SECRET"))
                checks.append(_check("webhook_signature", "Webhook signature test", sig_status, sig_message))
        tiers = _repo_stripe_tiers(project)
        if secret_key and tiers:
            missing = _missing_tier_products(secret_key, tiers)
            if missing is None:
                checks.append(_check("stripe_catalog", "Stripe products", "warn", "Could not list Stripe products"))
            elif missing:
                checks.append(
                    _check(
                        "stripe_catalog",
                        "Stripe products",
                        "fail",
                        "Stripe has no active product for: " + ", ".join(missing),
                        "Run setup to create them from the app's stripe.config.json",
                    )
                )
            else:
                checks.append(
                    _check("stripe_catalog", "Stripe products", "pass", f"All {len(tiers)} tier product(s) exist in Stripe")
                )

    db_key, db_url = _database_setting(value, variables if railway else {})
    if not db_url:
        if (entry.get("projectSlug") or "") in DATABASE_OPTIONAL_SLUGS:
            db_status, db_msg = "pass", "This app does not use a database"
        else:
            db_status, db_msg = "warn", "DATABASE_URL not set on the app's Railway service"
    elif db_url.lower().startswith("sqlite"):
        if "///" in db_url and re.match(r"^sqlite[^:]*:/{4}(data|app/data)/", db_url, re.I):
            db_status, db_msg = "pass", f"{db_key} is SQLite on an absolute path (needs a mounted volume to persist)"
        else:
            db_status, db_msg = "warn", f"{db_key} is a SQLite file on the container's disk, which is wiped on every deploy"
    elif not re.match(r"^(postgres(ql)?|mysql|mariadb|redis|mongodb(\+srv)?)://", db_url, re.I):
        db_status, db_msg = "fail", "DATABASE_URL is malformed (does not start with a valid scheme such as postgresql://)"
    else:
        db_status, db_msg = "pass", f"{db_key} is set"
    checks.append(_check("database", "Database", db_status, db_msg))

    if base_url:
        ok, message = _health_check(_join(base_url, str(entry.get("healthPath") or "/")))
        checks.append(_check("health", "Live health check", "pass" if ok else "fail", message))

    return {"checks": checks, "imported": imported, "railway": railway}


def _repo_stripe_config(project: Project) -> dict[str, Any] | None:
    """The app's own stripe.config.json from its GitHub repo; None when it has none (nothing is invented)."""
    import json

    from apps.api_transfer.github_import import fetch_repo_text_file
    from apps.stripe_core.stripe_config import normalize_stripe_config

    if not project.git_url:
        return None
    try:
        text = fetch_repo_text_file(project.git_url, "stripe.config.json")
        if not text:
            return None
        raw = json.loads(text)
        return normalize_stripe_config(raw) if isinstance(raw, dict) and raw.get("tiers") else None
    except Exception:
        return None


def _repo_stripe_tiers(project: Project) -> list[dict[str, Any]]:
    config = _repo_stripe_config(project)
    return list(config["tiers"]) if config else []


def _missing_tier_products(secret_key: str, tiers: list[dict[str, Any]]) -> list[str] | None:
    import stripe

    try:
        names = {p.name for p in stripe.Product.list(limit=100, active=True, api_key=secret_key).auto_paging_iter()}
    except stripe.StripeError:
        return None
    return [t["name"] for t in tiers if t["name"] not in names]


def provision_missing_catalog(project: Project) -> dict[str, Any]:
    """Create only the tier products/prices Stripe lacks, from the app's stripe.config.json."""
    import tempfile
    from pathlib import Path

    from apps.stripe_core.provision import ProvisionConfig, provision_catalog

    config = _repo_stripe_config(project)
    secret_key = (get_secret(project, "STRIPE_SECRET_KEY") or "").strip()
    if not config or not secret_key:
        raise ValueError("No stripe.config.json in the app's repo, or no STRIPE_SECRET_KEY in the vault")
    missing = _missing_tier_products(secret_key, config["tiers"]) or []
    tiers = [t for t in config["tiers"] if t["name"] in missing]
    if not tiers:
        return {"created": []}
    entry = catalog_entry_for(project) or {}
    base_url = str(entry.get("productionUrl") or config.get("appUrl") or "").rstrip("/")
    provision = config.get("provision") or {}
    with tempfile.TemporaryDirectory() as scratch:
        result = provision_catalog(
            secret_key,
            Path(scratch),
            project=project,
            config=ProvisionConfig(
                tiers=tiers,
                app_url=base_url,
                billing_portal_return_url=config.get("billingPortalReturnUrl") or f"{base_url}/stripe/account/",
                create_webhook=False,
                create_portal=bool(provision.get("createPortal", True)),
            ),
        )
    return {"created": [p["tier"] for p in result.prices if not p.get("reused")], "warnings": result.warnings}


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


_DB_SCHEME_PREFIX = re.compile(r"^[A-Za-z]*?((?:postgres(?:ql)?|mysql|mariadb|redis|mongodb(?:\+srv)?)://.+)$", re.I | re.S)


def repaired_database_url(value: str) -> str | None:
    """Strip stray characters before a valid scheme (e.g. ``URLpostgresql://``); None if not fixable."""
    value = (value or "").strip()
    if not value or _DB_SCHEME_PREFIX.match(value) is None or re.match(r"^(postgres|mysql|mariadb|redis|mongodb)", value, re.I):
        return None
    return _DB_SCHEME_PREFIX.match(value).group(1)


def _failed(outcome: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    return next((c for c in outcome["checks"] if c["id"] == check_id and c["status"] == "fail"), None)


def _auto_repair(project: Project, outcome: dict[str, Any]) -> list[dict[str, Any]]:
    """Fix what verification found wrong, using the Studio's own push and webhook features.

    Each repair runs only when its check fails, so a healthy app is never touched or redeployed.
    """
    from .env_push import _railway_environment_id, auto_push_railway_env, get_railway_env_vars, push_to_railway

    repairs: list[dict[str, Any]] = []
    railway = outcome.get("railway") or {}

    def attempt(name: str, action) -> None:
        try:
            repairs.append({"repair": name, "ok": True, "detail": action()})
        except Exception as exc:  # a failed repair is reported, never raised
            repairs.append({"repair": name, "ok": False, "detail": str(exc)[:300]})

    signature = _failed(outcome, "webhook_signature")
    secret_rejected = bool(signature and "rejected the signing secret" in signature["message"])
    if (_failed(outcome, "stripe_webhook") or secret_rejected) and get_secret(project, "STRIPE_SECRET_KEY"):
        attempt("register_stripe_webhook", lambda: register_webhook(project))

    if _failed(outcome, "stripe_catalog"):
        attempt("provision_stripe_catalog", lambda: provision_missing_catalog(project))

    if (_failed(outcome, "stripe_keys") or _failed(outcome, "webhook_secret")) and not repairs_has(repairs, "register_stripe_webhook"):
        attempt("sync_vault_to_railway", lambda: auto_push_railway_env(project).get("message", "pushed"))

    if _failed(outcome, "database") and railway.get("serviceId"):
        def fix_database() -> str:
            token = _railway_token(project)
            if not token:
                raise ValueError("No Railway token available")
            env_id = railway.get("environmentId") or _railway_environment_id(token, railway["projectId"])
            current = get_railway_env_vars(token, railway["projectId"], railway["serviceId"], env_id).get("DATABASE_URL", "")
            fixed = repaired_database_url(current)
            if not fixed:
                raise ValueError("DATABASE_URL is malformed and cannot be repaired automatically")
            push_to_railway(token, railway["projectId"], railway["serviceId"], {"DATABASE_URL": fixed}, env_id, preserve_existing=True)
            set_secret(project, "DATABASE_URL", fixed)
            return "Removed stray characters before the DATABASE_URL scheme"

        attempt("repair_database_url", fix_database)
    return repairs


def repairs_has(repairs: list[dict[str, Any]], name: str) -> bool:
    return any(r["repair"] == name for r in repairs)


def run_cloud_setup(project: Project, *, user=None) -> PipelineRun:
    """Verify the project and record the result as a completed pipeline run."""
    started = timezone.now()
    try:
        outcome = verify_project(project)
        repairs = _auto_repair(project, outcome)
        if repairs:
            repaired = verify_project(project)
            repaired["imported"] = sorted(set(outcome["imported"]) | set(repaired["imported"]))
            outcome = repaired
        outcome["repairs"] = repairs
        error = ""
    except Exception as exc:  # recorded on the run instead of a 500
        outcome = {"checks": [], "imported": [], "railway": {}, "repairs": []}
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
            "repairs": outcome.get("repairs", []),
        },
        error_message=error,
        readiness_score=None if error else score,
        started_at=started,
        completed_at=timezone.now(),
    )
