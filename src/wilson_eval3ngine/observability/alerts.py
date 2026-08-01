"""
Alert rule definitions with severity, deduplication, and runbook links.

TODO 52 - T8.1.2: Alerting configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..telemetry import is_safe_for_telemetry
from .sli_slo import AlertSeverity


class AlertCategory(StrEnum):
    """Categories of alerts."""
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    INTEGRITY = "integrity"
    SECURITY = "security"
    COST = "cost"


@dataclass(frozen=True, slots=True)
class AlertRule:
    """Production alert rule with deduplication and routing."""

    alert_id: str
    category: AlertCategory
    severity: AlertSeverity
    sli_id: str
    summary: str
    description: str
    query: str
    threshold: float
    duration_seconds: int = 300  # 5 minutes default
    alert_window_minutes: int = 60  # Evaluation window for alert
    owner: str = ""
    runbook_url: str = ""
    recovery_condition: str = ""
    fingerprint_fields: list[str] = field(default_factory=lambda: ["project_id", "experiment_id"])
    suppressed: bool = False  # Alert suppressed during maintenance

    def evaluate(self, value: float | None) -> bool:
        """Check if alert should fire."""
        if value is None:
            return False
        return value < self.threshold

    def should_route_to_page(self) -> bool:
        """Determine if alert should trigger paging based on severity."""
        return self.severity == AlertSeverity.PAGE

    def should_route_to_ticket(self) -> bool:
        """Determine if alert should create ticket based on severity."""
        return self.severity in {AlertSeverity.TICKET, AlertSeverity.PAGE}

    def validate_labels(self, labels: dict[str, Any]) -> tuple[bool, str]:
        """Validate alert labels for safety and correctness.

        Security: Prevents injection of unsafe labels into alert routing.
        Returns (is_valid, error_message).
        """
        # Check for attacker-controlled labels that could affect routing
        unsafe_keys = {"severity", "owner", "runbook", "category"}
        for key in unsafe_keys:
            if key in labels:
                return False, f"Unsafe label key '{key}' cannot be overridden"

        # Validate label values are safe
        for key, value in labels.items():
            if not is_safe_for_telemetry(value):
                return False, f"Unsafe label value for key '{key}'"

        return True, ""

    def to_prometheus_rule(self) -> dict[str, Any]:
        """Convert to Prometheus alert rule format."""
        return {
            "alert": self.alert_id,
            "expr": self.query,
            "for": f"{self.duration_seconds}s",
            "labels": {
                "severity": self.severity.value,
                "category": self.category.value,
                "owner": self.owner,
                "runbook": self.runbook_url,
            },
            "annotations": {
                "summary": self.summary,
                "description": self.description,
                "recovery_condition": self.recovery_condition,
            },
        }


def get_alert_rules() -> list[AlertRule]:
    """Get all alert rules for the platform."""
    return [
        # API Availability Alerts
        AlertRule(
            alert_id="APIAvailabilityBreaching",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="sli-api-availability-v1",
            summary="API availability below 99.9%",
            description="API success rate has dropped below target. Check for provider outages or system errors.",
            query="we3_sli_api_availability_v1 < 0.999",
            threshold=0.999,
            duration_seconds=300,
            alert_window_minutes=60,
            owner="Platform Team",
            runbook_url="/docs/operations/sev-incidents.md#provider-outage-response",
            recovery_condition="we3_sli_api_availability_v1 >= 0.9995 for 10m",
        ),
        AlertRule(
            alert_id="APIAvailabilityWarning",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.TICKET,
            sli_id="sli-api-availability-v1",
            summary="API availability approaching breach threshold",
            description="API success rate below warning threshold (99.95%). Monitor closely.",
            query="we3_sli_api_availability_v1 < 0.9995",
            threshold=0.9995,
            duration_seconds=600,
            alert_window_minutes=60,
            owner="Platform Team",
            runbook_url="/docs/operations/sev-incidents.md#provider-outage-response",
            recovery_condition="we3_sli_api_availability_v1 >= 0.999 for 15m",
        ),
        # Evidence Durability Alerts
        AlertRule(
            alert_id="EvidenceDurabilityBreaching",
            category=AlertCategory.INTEGRITY,
            severity=AlertSeverity.PAGE,
            sli_id="sli-evidence-durability-v1",
            summary="Evidence durability below 99.99%",
            description=(
                "Records accepted but not persisted. "
                "Risk of data loss. Check database connectivity and disk space."
            ),
            query="we3_sli_evidence_durability_v1 < 0.9999",
            threshold=0.9999,
            duration_seconds=300,
            owner="SRE Team",
            runbook_url="/docs/operations/sev-incidents.md#evidence-corruption-response",
            recovery_condition="we3_sli_evidence_durability_v1 >= 0.99995 for 10m",
        ),
        # Queue Latency Alerts
        AlertRule(
            alert_id="QueueStartLatencyHigh",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.TICKET,
            sli_id="sli-queue-start-latency-p95-v1",
            summary="Queue start latency approaching threshold",
            description=(
                "P95 queue start latency above 3 minutes. "
                "Check worker capacity and job backlog."
            ),
            query="we3_sli_queue_start_latency_p95_v1 > 3",
            threshold=3.0,  # 3 minutes in minutes
            duration_seconds=300,
            owner="SRE Team",
            runbook_url="/docs/operations/sev-incidents.md#queue-backlog-response",
            recovery_condition="we3_sli_queue_start_latency_p95_v1 <= 2 for 10m",
        ),
        AlertRule(
            alert_id="QueueStartLatencyBreaching",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.PAGE,
            sli_id="sli-queue-start-latency-p95-v1",
            summary="Queue start latency breaching SLO",
            description="P95 queue start latency exceeds 5 minutes. Immediate investigation required.",
            query="we3_sli_queue_start_latency_p95_v1 > 5",
            threshold=5.0,
            duration_seconds=180,
            owner="SRE Team",
            runbook_url="/docs/operations/sev-incidents.md#queue-backlog-response",
            recovery_condition="we3_sli_queue_start_latency_p95_v1 <= 3 for 10m",
        ),
        # Grading Duration Alerts
        AlertRule(
            alert_id="GradingDurationHigh",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.TICKET,
            sli_id="sli-grading-duration-p95-v1",
            summary="Grading duration high",
            description="P95 grading duration above 1 minute. Check grader performance and resource usage.",
            query="we3_sli_grading_duration_p95_v1 > 60",
            threshold=60.0,  # 1 minute in seconds
            duration_seconds=300,
            owner="Evaluation Team",
            runbook_url="/docs/operations/sev-incidents.md#grading-drift-response",
            recovery_condition="we3_sli_grading_duration_p95_v1 <= 30 for 10m",
        ),
        AlertRule(
            alert_id="GradingDurationBreaching",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.PAGE,
            sli_id="sli-grading-duration-p95-v1",
            summary="Grading duration breaching SLO",
            description="P95 grading duration exceeds 2 minutes. Check for stuck processes or resource exhaustion.",
            query="we3_sli_grading_duration_p95_v1 > 120",
            threshold=120.0,  # 2 minutes in seconds
            duration_seconds=180,
            owner="Evaluation Team",
            runbook_url="/docs/operations/sev-incidents.md#grading-drift-response",
            recovery_condition="we3_sli_grading_duration_p95_v1 <= 60 for 10m",
        ),
        # Report Generation Alerts
        AlertRule(
            alert_id="ReportGenerationSlow",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.TICKET,
            sli_id="sli-report-generation-p99-v1",
            summary="Report generation slow",
            description="P99 report generation time above 5 minutes. Check database query performance.",
            query="we3_sli_report_generation_p99_v1 > 300",
            threshold=300.0,  # 5 minutes in seconds
            duration_seconds=300,
            owner="SRE Team",
            runbook_url="/docs/operations/sev-incidents.md#report-generation-response",
            recovery_condition="we3_sli_report_generation_p99_v1 <= 180 for 10m",
        ),
        AlertRule(
            alert_id="ReportGenerationBreaching",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.PAGE,
            sli_id="sli-report-generation-p99-v1",
            summary="Report generation breaching SLO",
            description=(
                "P99 report generation time exceeds 10 minutes. "
                "Check for database lock contention or missing indexes."
            ),
            query="we3_sli_report_generation_p99_v1 > 600",
            threshold=600.0,  # 10 minutes in seconds
            duration_seconds=180,
            owner="SRE Team",
            runbook_url="/docs/operations/sev-incidents.md#report-generation-response",
            recovery_condition="we3_sli_report_generation_p99_v1 <= 300 for 10m",
        ),
        # Hash Verification Alerts
        AlertRule(
            alert_id="HashVerificationFailed",
            category=AlertCategory.INTEGRITY,
            severity=AlertSeverity.PAGE,
            sli_id="sli-hash-verification-v1",
            summary="Scheduled hash verification failed",
            description="Evidence integrity verification failed. Possible corruption or missing artifacts.",
            query="we3_sli_hash_verification_v1 < 1.0",
            threshold=1.0,
            duration_seconds=600,
            owner="Security Team",
            runbook_url="/docs/operations/sev-incidents.md#evidence-corruption-response",
            recovery_condition="we3_sli_hash_verification_v1 == 1.0 for 30m",
        ),
        AlertRule(
            alert_id="HashVerificationJobFailed",
            category=AlertCategory.INTEGRITY,
            severity=AlertSeverity.PAGE,
            sli_id="sli-hash-verification-v1",
            summary="Hash verification job itself failed",
            description=(
                "The scheduled hash verification job has failed to execute. "
                "Check cron and job runner."
            ),
            query="absent(we3_sli_hash_verification_v1[24h])",
            threshold=0.0,
            duration_seconds=3600,
            owner="Security Team",
            runbook_url="/docs/operations/sev-incidents.md#evidence-corruption-response",
            recovery_condition="we3_sli_hash_verification_v1 > 0",
        ),
        # Provider Error Alerts
        AlertRule(
            alert_id="ProviderErrorRateHigh",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.TICKET,
            sli_id="sli-api-availability-v1",  # Uses same SLI as errors affect availability
            summary="Provider error rate elevated",
            description="Provider errors detected. Check provider health and credentials.",
            query="rate(we3_provider_errors_total[5m]) > 0.05",
            threshold=0.05,
            duration_seconds=300,
            owner="Platform Team",
            runbook_url="/docs/operations/sev-incidents.md#provider-outage-response",
            recovery_condition="rate(we3_provider_errors_total[5m]) < 0.01 for 10m",
        ),
        # Critical Review Alerts
        AlertRule(
            alert_id="CriticalReviewBacklog",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.TICKET,
            sli_id="sli-queue-start-latency-p95-v1",  # Proxy for review backlog
            summary="Critical review backlog detected",
            description="Unresolved critical review tasks exceeding threshold. Check reviewer capacity.",
            query="we3_unresolved_critical_reviews > 10",
            threshold=10.0,
            duration_seconds=600,
            owner="Governance Team",
            runbook_url="/docs/operations/sev-incidents.md#review-backlog-response",
            recovery_condition="we3_unresolved_critical_reviews <= 5 for 30m",
        ),
    ]


# Alert fingerprint generation for deduplication
def compute_alert_fingerprint(alert: AlertRule, labels: dict[str, Any]) -> str:
    """Compute unique fingerprint for alert deduplication."""
    from ..util import sha256_hex
    selected_labels = {
        k: v for k, v in labels.items()
        if k in alert.fingerprint_fields
    }
    return sha256_hex(selected_labels)


def get_alerts_for_sli(sli_id: str) -> list[AlertRule]:
    """Get all alert rules associated with a given SLI."""
    return [rule for rule in get_alert_rules() if rule.sli_id == sli_id]


def get_alert_by_id(alert_id: str) -> AlertRule | None:
    """Get a specific alert rule by ID."""
    for rule in get_alert_rules():
        if rule.alert_id == alert_id:
            return rule
    return None


def validate_all_alert_labels(
    label_overrides: dict[str, dict[str, Any]]
) -> dict[str, tuple[bool, str]]:
    """Validate labels for all alerts.

    Security: Prevents label injection attacks on alert routing.
    Returns dict mapping alert_id to (is_valid, error_message).
    """
    results = {}
    for rule in get_alert_rules():
        if rule.alert_id in label_overrides:
            labels = label_overrides[rule.alert_id]
            results[rule.alert_id] = rule.validate_labels(labels)
    return results


__all__ = [
    "AlertCategory",
    "AlertRule",
    "get_alert_rules",
    "get_alerts_for_sli",
    "get_alert_by_id",
    "validate_all_alert_labels",
    "compute_alert_fingerprint",
]