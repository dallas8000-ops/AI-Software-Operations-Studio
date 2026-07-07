"""Post-deploy Stripe webhook health — API metadata + delivery failure detection."""

from __future__ import annotations

from typing import Any

import stripe

from apps.projects.models import Project
from apps.stripe_core.hub_keys import resolve_expected_webhook_url
from apps.stripe_core.portfolio_catalog import is_stripe_exempt_slug
from apps.stripe_core.webhook_delivery import assess_webhook_delivery
from apps.vault.models import get_secret


def webhook_health(project: Project) -> dict[str, Any]:
    secret = get_secret(project, "STRIPE_SECRET_KEY")
    if not secret:
        raise RuntimeError("STRIPE_SECRET_KEY not in vault")

    stripe.api_key = secret
    expected = resolve_expected_webhook_url(project) or None

    endpoints = stripe.WebhookEndpoint.list(limit=10)
    endpoint_rows: list[dict[str, Any]] = []
    for ep in endpoints.data:
        row = {
            "id": ep.id,
            "url": ep.url,
            "status": ep.status,
            "enabledEvents": len(ep.enabled_events or []),
            "matchesExpected": ep.url == expected if expected else None,
        }
        endpoint_rows.append(row)

    recent_types: dict[str, int] = {}
    recent_event_count: int | None = 0
    delivery_evidence: dict[str, Any] = {
        "status": "inactive",
        "level": "unknown",
        "recentStripeEventCount": 0,
        "message": (
            "No recent Stripe events found. That is normal for a quiet account, "
            "but it does not prove webhook deliveries are succeeding."
        ),
    }
    try:
        events = stripe.Event.list(limit=25)
        for ev in events.data:
            recent_types[ev.type] = recent_types.get(ev.type, 0) + 1
        recent_event_count = len(events.data)
        if recent_event_count > 0:
            delivery_evidence = {
                "status": "activity_seen",
                "level": "info",
                "recentStripeEventCount": recent_event_count,
                "message": (
                    "Recent Stripe account events exist. Confirm endpoint deliveries in "
                    "Stripe Dashboard before treating delivery error rate as healthy."
                ),
            }
    except Exception:
        recent_event_count = None
        delivery_evidence = {
            "status": "unknown",
            "level": "unknown",
            "recentStripeEventCount": None,
            "message": "Could not read recent Stripe events, so delivery activity is unknown.",
        }

    delivery_assessment = None
    delivery_stats = None
    signature_probe = None
    if not is_stripe_exempt_slug(project.slug):
        try:
            assessment = assess_webhook_delivery(project)
            delivery_assessment = assessment.to_dict()
            delivery_stats = assessment.deliveryStats.to_dict() if assessment.deliveryStats else None
            signature_probe = assessment.signatureProbe.to_dict() if assessment.signatureProbe else None
            if assessment.deliveryStats and assessment.deliveryStats.sampleSufficient:
                rate = assessment.deliveryStats.successRate
                if rate is not None:
                    success_pct = round(rate * 100, 1)
                    delivery_evidence = {
                        "status": "failing" if assessment.deliveryStats.highFailureRate else "healthy",
                        "level": "error" if assessment.deliveryStats.highFailureRate else "info",
                        "recentStripeEventCount": assessment.deliveryStats.totalEvents,
                        "successRate": success_pct,
                        "failedDeliveries": assessment.deliveryStats.failedDeliveries,
                        "message": (
                            f"Webhook delivery success ~{success_pct}% over last "
                            f"{assessment.deliveryStats.lookbackHours}h "
                            f"({assessment.deliveryStats.failedDeliveries} failed)."
                            if assessment.deliveryStats.highFailureRate
                            else f"Webhook delivery success ~{success_pct}% over last "
                            f"{assessment.deliveryStats.lookbackHours}h."
                        ),
                    }
        except Exception:
            delivery_assessment = None

    issues = []
    if expected and not any(r.get("matchesExpected") for r in endpoint_rows):
        issues.append(
            {
                "severity": "warning",
                "message": f"No webhook endpoint matches expected URL {expected}",
                "fix": "Run provision-stripe or update webhook in Stripe Dashboard",
                "autoFixable": True,
                "fixAction": "provision-stripe",
            }
        )
    disabled = [r for r in endpoint_rows if r.get("status") != "enabled"]
    for row in disabled:
        issues.append(
            {
                "severity": "error",
                "message": f"Webhook {row['id']} is {row['status']}",
                "fix": "Enable endpoint in Stripe Dashboard",
                "autoFixable": False,
            }
        )

    if delivery_assessment:
        for issue in delivery_assessment.get("issues") or []:
            issues.append(
                {
                    "severity": issue.get("severity", "warning"),
                    "message": issue.get("message", ""),
                    "fix": issue.get("fix", ""),
                    "autoFixable": bool(issue.get("autoFixable")),
                    "fixAction": "repair-webhook-delivery" if issue.get("autoFixable") else None,
                    "code": issue.get("code"),
                }
            )

    healthy = not any(i.get("severity") == "error" for i in issues)

    return {
        "expectedWebhookUrl": expected,
        "endpoints": endpoint_rows,
        "recentEventTypes": recent_types,
        "recentStripeEventCount": recent_event_count,
        "deliveryEvidence": delivery_evidence,
        "deliveryStats": delivery_stats,
        "signatureProbe": signature_probe,
        "deliveryAssessment": delivery_assessment,
        "issues": issues,
        "healthy": healthy,
        "autoRepairRecommended": bool(delivery_assessment and delivery_assessment.get("needsRepair")),
    }
