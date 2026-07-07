"""Webhook delivery monitoring, signed live probes, and automatic repair."""

from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import stripe

from apps.projects.models import Project
from apps.stripe_core.hub_keys import HUB_SLUG, resolve_expected_webhook_url
from apps.stripe_core.portfolio_catalog import is_stripe_exempt_slug
from apps.vault.models import get_secret, set_secret

DEFAULT_FAILURE_RATE_THRESHOLD = 0.30
DEFAULT_MIN_SAMPLE_EVENTS = 5
DEFAULT_LOOKBACK_HOURS = 168  # 7 days


@dataclass
class DeliveryStats:
    lookbackHours: int
    totalEvents: int
    failedDeliveries: int
    successRate: float | None
    sampleSufficient: bool
    highFailureRate: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignatureProbe:
    url: str
    httpStatus: int | None
    classification: str
    signatureValid: bool
    reachable: bool
    bodySnippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeliveryAssessment:
    projectSlug: str
    expectedWebhookUrl: str | None
    deliveryStats: DeliveryStats | None
    signatureProbe: SignatureProbe | None
    needsRepair: bool
    repairReason: str | None
    autoFixable: bool
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.deliveryStats:
            payload["deliveryStats"] = self.deliveryStats.to_dict()
        if self.signatureProbe:
            payload["signatureProbe"] = self.signatureProbe.to_dict()
        return payload


def _webhook_secret_keys(project: Project) -> tuple[str, ...]:
    if project.slug == HUB_SLUG:
        return ("SAAS_STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET")
    return ("STRIPE_WEBHOOK_SECRET",)


def get_webhook_secret(project: Project) -> str:
    for key in _webhook_secret_keys(project):
        value = get_secret(project, key)
        if value:
            return value.strip()
    return ""


def store_webhook_secret(project: Project, secret: str) -> None:
    secret = secret.strip()
    if not secret:
        return
    if project.slug == HUB_SLUG:
        set_secret(project, "SAAS_STRIPE_WEBHOOK_SECRET", secret)
    set_secret(project, "STRIPE_WEBHOOK_SECRET", secret)


def fetch_delivery_stats(
    project: Project,
    *,
    hours: int = DEFAULT_LOOKBACK_HOURS,
    failure_threshold: float = DEFAULT_FAILURE_RATE_THRESHOLD,
    min_sample: int = DEFAULT_MIN_SAMPLE_EVENTS,
) -> DeliveryStats | None:
    """Use Stripe Event delivery_success filter to estimate endpoint failure rate."""
    secret = get_secret(project, "STRIPE_SECRET_KEY")
    if not secret:
        return None

    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    stripe.api_key = secret

    try:
        all_events = stripe.Event.list(limit=100, created={"gte": since})
        failed_events = stripe.Event.list(limit=100, delivery_success=False, created={"gte": since})
    except stripe.StripeError:
        return None

    total = len(all_events.data)
    failed = len(failed_events.data)
    success_rate = round((total - failed) / total, 4) if total else None
    sample_sufficient = total >= min_sample
    high_failure = bool(
        sample_sufficient
        and success_rate is not None
        and success_rate < (1.0 - failure_threshold)
    )

    return DeliveryStats(
        lookbackHours=hours,
        totalEvents=total,
        failedDeliveries=failed,
        successRate=success_rate,
        sampleSufficient=sample_sufficient,
        highFailureRate=high_failure,
    )


def _sign_payload(payload: str, secret: str) -> str:
    ts = str(int(time.time()))
    signed = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={signed}"


def _classify_probe_status(status: int | None, body: str) -> tuple[str, bool]:
    snippet = (body or "").lower()
    if status is None:
        return "unreachable", False
    if status == 403 and "csrf" in snippet:
        return "csrf_blocked", False
    if status == 404:
        return "route_missing", False
    if status == 503:
        return "not_configured", False
    if status == 400 and ("invalid payload" in snippet or "signature" in snippet):
        return "signature_mismatch", False
    if status == 500:
        return "handler_error", True
    if 200 <= status < 300:
        return "ok", True
    return "unknown", False


def probe_signed_webhook(project: Project, *, timeout: float = 12.0) -> SignatureProbe | None:
    """POST a signed probe event to the live webhook URL using vault whsec_."""
    expected = resolve_expected_webhook_url(project)
    whsec = get_webhook_secret(project)
    if not expected or not whsec or not whsec.startswith("whsec_"):
        return None

    event_id = f"evt_probe_{int(time.time())}"
    payload = json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": "customer.updated",
            "data": {"object": {"id": "cus_probe", "object": "customer"}},
        }
    )
    signature = _sign_payload(payload, whsec)
    normalized = expected if expected.endswith("/") else f"{expected}/"

    for attempt_url in (normalized, normalized.rstrip("/")):
        try:
            req = Request(
                attempt_url,
                data=payload.encode(),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": signature,
                    "User-Agent": "stripe-installer-delivery-probe/1.0",
                },
            )
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read(300).decode("utf-8", errors="replace")
                classification, signature_valid = _classify_probe_status(resp.status, body)
                return SignatureProbe(
                    url=attempt_url,
                    httpStatus=resp.status,
                    classification=classification,
                    signatureValid=signature_valid,
                    reachable=True,
                    bodySnippet=body[:120],
                )
        except HTTPError as exc:
            body = exc.read(300).decode("utf-8", errors="replace") if exc.fp else ""
            classification, signature_valid = _classify_probe_status(exc.code, body)
            return SignatureProbe(
                url=attempt_url,
                httpStatus=exc.code,
                classification=classification,
                signatureValid=signature_valid,
                reachable=True,
                bodySnippet=body[:120],
            )
        except URLError:
            continue
        except Exception:
            continue

    return SignatureProbe(
        url=expected,
        httpStatus=None,
        classification="unreachable",
        signatureValid=False,
        reachable=False,
    )


def assess_webhook_delivery(project: Project) -> DeliveryAssessment:
    """Assess delivery health using Stripe stats + signed live probe."""
    expected = resolve_expected_webhook_url(project)
    issues: list[dict[str, Any]] = []

    if is_stripe_exempt_slug(project.slug):
        return DeliveryAssessment(
            projectSlug=project.slug,
            expectedWebhookUrl=expected,
            deliveryStats=None,
            signatureProbe=None,
            needsRepair=False,
            repairReason=None,
            autoFixable=False,
            issues=issues,
        )

    stats = fetch_delivery_stats(project)
    probe = probe_signed_webhook(project)

    needs_repair = False
    repair_reason: str | None = None
    auto_fixable = False

    if stats and stats.highFailureRate:
        rate_pct = round((1 - (stats.successRate or 0)) * 100, 1)
        issues.append(
            {
                "severity": "error",
                "code": "webhook_high_failure_rate",
                "message": (
                    f"Stripe webhook delivery success rate is ~{100 - rate_pct:.1f}% "
                    f"({stats.failedDeliveries}/{stats.totalEvents} failed in last {stats.lookbackHours}h)"
                ),
                "fix": "Run automatic webhook repair to rotate signing secret and push to Railway",
                "autoFixable": True,
            }
        )
        needs_repair = True
        repair_reason = "high_failure_rate"
        auto_fixable = True

    if probe:
        if probe.classification == "signature_mismatch":
            issues.append(
                {
                    "severity": "error",
                    "code": "webhook_signature_mismatch",
                    "message": "Live webhook rejected the vault signing secret (HTTP 400)",
                    "fix": "Re-register webhook, sync whsec_ to vault and Railway",
                    "autoFixable": True,
                }
            )
            needs_repair = True
            repair_reason = repair_reason or "signature_mismatch"
            auto_fixable = True
        elif probe.classification == "route_missing":
            issues.append(
                {
                    "severity": "error",
                    "code": "webhook_route_missing",
                    "message": f"Webhook route not found at {probe.url}",
                    "fix": "Deploy app with matching webhook route or update portfolio registry URL",
                    "autoFixable": False,
                }
            )
            needs_repair = True
            repair_reason = repair_reason or "route_missing"
        elif probe.classification == "handler_error":
            issues.append(
                {
                    "severity": "error",
                    "code": "webhook_handler_error",
                    "message": "Webhook route reachable but returned HTTP 500 — check app logs",
                    "fix": "Inspect Railway logs for billing webhook handler exceptions",
                    "autoFixable": False,
                }
            )
            needs_repair = True
            repair_reason = repair_reason or "handler_error"
        elif probe.classification == "unreachable":
            issues.append(
                {
                    "severity": "warning",
                    "code": "webhook_unreachable",
                    "message": f"Could not reach webhook URL {probe.url}",
                    "fix": "Confirm production URL and TLS; redeploy if hosting is down",
                    "autoFixable": False,
                }
            )

    return DeliveryAssessment(
        projectSlug=project.slug,
        expectedWebhookUrl=expected,
        deliveryStats=stats,
        signatureProbe=probe,
        needsRepair=needs_repair and auto_fixable,
        repairReason=repair_reason,
        autoFixable=auto_fixable,
        issues=issues,
    )


def auto_repair_webhook_delivery(project: Project) -> dict[str, Any]:
    """Rotate webhook signing secret, store in vault, and push to Railway."""
    from apps.stripe_core.hub_keys import get_hub_project
    from apps.stripe_core.secret_placement import repair_project_secret_placement

    assessment = assess_webhook_delivery(project)
    if not assessment.needsRepair:
        return {
            "ok": True,
            "skipped": True,
            "message": "No auto-fixable webhook delivery issue detected",
            "assessment": assessment.to_dict(),
        }

    hub = get_hub_project(project.owner)
    repair = repair_project_secret_placement(project, hub=hub)
    post = assess_webhook_delivery(project)

    return {
        "ok": bool(repair.get("ok")),
        "repairReason": assessment.repairReason,
        "repair": repair,
        "assessmentBefore": assessment.to_dict(),
        "assessmentAfter": post.to_dict(),
    }


def assess_and_repair_if_needed(project: Project) -> dict[str, Any]:
    """Assess delivery health and auto-repair when failure rate or signature mismatch is detected."""
    assessment = assess_webhook_delivery(project)
    if not assessment.needsRepair:
        return {"ok": True, "repaired": False, "assessment": assessment.to_dict()}
    repair = auto_repair_webhook_delivery(project)
    return {
        "ok": repair.get("ok", False),
        "repaired": True,
        "assessment": assessment.to_dict(),
        "repair": repair,
    }
