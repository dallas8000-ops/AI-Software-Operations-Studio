"""Anomaly detection for webhooks, payments, and system behavior."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

import stripe

from apps.projects.models import Project
from apps.vault.models import get_secret


@dataclass
class Anomaly:
    """Detected anomaly."""
    type: str
    severity: str  # low, medium, high
    description: str
    metric: str
    value: Any
    expected_range: tuple[Any, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "metric": self.metric,
            "value": self.value,
            "expectedRange": self.expected_range,
            "timestamp": self.timestamp,
        }


@dataclass
class AnomalyReport:
    """Report of detected anomalies."""
    project_id: str
    project_slug: str
    anomalies: list[Anomaly]
    summary: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectId": str(self.project_id),
            "projectSlug": self.project_slug,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


def _detect_webhook_failure_anomalies(project: Project) -> list[Anomaly]:
    """Detect anomalies in webhook failure patterns."""
    anomalies = []
    secret = get_secret(project, "STRIPE_SECRET_KEY")

    if not secret:
        return anomalies

    try:
        from apps.stripe_core.webhook_delivery import assess_webhook_delivery

        assessment = assess_webhook_delivery(project)
        stats = assessment.deliveryStats
        probe = assessment.signatureProbe

        if stats and stats.highFailureRate and stats.successRate is not None:
            failure_rate = 1.0 - stats.successRate
            anomalies.append(
                Anomaly(
                    type="webhook_delivery_failure_rate",
                    severity="high" if failure_rate > 0.5 else "medium",
                    description=(
                        f"Stripe webhook delivery failing ~{failure_rate:.0%} "
                        f"({stats.failedDeliveries}/{stats.totalEvents} in {stats.lookbackHours}h)"
                    ),
                    metric="delivery_failure_rate",
                    value=failure_rate,
                    expected_range=(0.0, 0.1),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        if probe and probe.classification == "signature_mismatch":
            anomalies.append(
                Anomaly(
                    type="webhook_signature_mismatch",
                    severity="high",
                    description="Vault webhook secret rejected by live endpoint",
                    metric="signature_probe",
                    value=probe.classification,
                    expected_range=("ok", "ok"),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        stripe.api_key = secret

        # Get recent events for payment-pattern anomalies
        events = stripe.Event.list(
            limit=100,
            created={"gt": int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())},
        )

        event_counts = defaultdict(int)
        for event in events.data:
            event_counts[event.type] += 1

        total_events = len(events.data)
        if total_events > 0:
            failure_events = sum(
                count for typ, count in event_counts.items() if "failed" in typ.lower() or "error" in typ.lower()
            )
            failure_rate = failure_events / total_events

            if failure_rate > 0.1:
                anomalies.append(
                    Anomaly(
                        type="webhook_failure_rate",
                        severity="high" if failure_rate > 0.25 else "medium",
                        description=f"High account event failure rate detected: {failure_rate:.1%}",
                        metric="failure_rate",
                        value=failure_rate,
                        expected_range=(0.0, 0.1),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )

    except Exception:
        pass

    return anomalies


def _detect_payment_anomalies(project: Project) -> list[Anomaly]:
    """Detect anomalies in payment patterns."""
    anomalies = []
    secret = get_secret(project, "STRIPE_SECRET_KEY")

    if not secret:
        return anomalies

    try:
        stripe.api_key = secret

        # Get recent charges
        charges = stripe.Charge.list(limit=100, created={"gt": int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())})

        if not charges.data:
            return anomalies

        # Analyze charge amounts
        amounts = [charge.amount for charge in charges.data if charge.amount]
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            max_amount = max(amounts)

            # Check for unusually large charges
            if max_amount > avg_amount * 10:
                anomalies.append(Anomaly(
                    type="unusually_large_payment",
                    severity="medium",
                    description=f"Payment amount significantly above average: ${max_amount/100:.2f}",
                    metric="max_charge_amount",
                    value=max_amount,
                    expected_range=(avg_amount * 0.5, avg_amount * 3),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))

        # Check failure rate
        failed_charges = sum(1 for charge in charges.data if charge.status == "failed")
        failure_rate = failed_charges / len(charges.data)

        if failure_rate > 0.05:  # More than 5% failures
            anomalies.append(Anomaly(
                type="payment_failure_rate",
                severity="high" if failure_rate > 0.15 else "medium",
                description=f"High payment failure rate: {failure_rate:.1%}",
                metric="payment_failure_rate",
                value=failure_rate,
                expected_range=(0.0, 0.05),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

    except Exception:
        pass

    return anomalies


def _detect_api_rate_anomalies(project: Project) -> list[Anomaly]:
    """Detect anomalies in API usage patterns."""
    anomalies = []

    # Check for rapid successive API calls (would need logging in production)
    # For now, we'll check vault access patterns
    from apps.vault.models import VaultSecret

    try:
        recent_secrets = VaultSecret.objects.filter(project=project).order_by("-updated_at")[:10]
        if recent_secrets:
            # Check if secrets were updated very frequently
            timestamps = [s.updated_at for s in recent_secrets if s.updated_at]
            if len(timestamps) > 1:
                time_diffs = [(timestamps[i] - timestamps[i+1]).total_seconds() for i in range(len(timestamps)-1)]
                avg_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0

                if avg_diff < 60:  # Average update less than 1 minute apart
                    anomalies.append(Anomaly(
                        type="rapid_configuration_changes",
                        severity="low",
                        description=f"Rapid configuration changes detected (avg {avg_diff:.0f}s apart)",
                        metric="config_update_frequency",
                        value=avg_diff,
                        expected_range=(60, 86400),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
    except Exception:
        pass

    return anomalies


def run_anomaly_detection(project: Project) -> AnomalyReport:
    """Run comprehensive anomaly detection on a project."""
    anomalies = []

    # Run all anomaly detectors
    anomalies.extend(_detect_webhook_failure_anomalies(project))
    anomalies.extend(_detect_payment_anomalies(project))
    anomalies.extend(_detect_api_rate_anomalies(project))

    # Calculate summary
    severity_counts = {"low": 0, "medium": 0, "high": 0}
    for anomaly in anomalies:
        severity_counts[anomaly.severity] += 1

    summary = {
        "totalAnomalies": len(anomalies),
        "severityBreakdown": severity_counts,
        "overallRisk": "high" if severity_counts["high"] > 0 else "medium" if severity_counts["medium"] > 2 else "low",
    }

    return AnomalyReport(
        project_id=project.id,
        project_slug=project.slug,
        anomalies=anomalies,
        summary=summary,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def run_all_projects_anomaly_detection() -> dict[str, Any]:
    """Run anomaly detection on all projects."""
    from apps.vault.models import VaultSecret

    project_ids = (
        VaultSecret.objects.filter(key_name="STRIPE_SECRET_KEY")
        .values_list("project_id", flat=True)
        .distinct()
    )

    reports = []
    total_anomalies = 0
    high_risk_projects = 0

    for pid in project_ids:
        try:
            project = Project.objects.get(id=pid)
            report = run_anomaly_detection(project)
            reports.append(report.to_dict())
            total_anomalies += len(report.anomalies)

            if report.summary.get("overallRisk") == "high":
                high_risk_projects += 1
        except Project.DoesNotExist:
            continue

    return {
        "summary": {
            "totalProjects": len(reports),
            "totalAnomalies": total_anomalies,
            "highRiskProjects": high_risk_projects,
        },
        "reports": reports,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
