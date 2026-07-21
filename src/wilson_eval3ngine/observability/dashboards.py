"""
Dashboard configurations for Grafana/Prometheus.

TODO 52 - T8.1.2: Dashboard definitions for service health, queue, provider, grading, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DashboardCategory(StrEnum):
    """Categories of dashboards."""
    SERVICE_HEALTH = "service_health"
    QUEUE_METRICS = "queue_metrics"
    PROVIDER_ERRORS = "provider_errors"
    GRADING_REVIEW = "grading_review"
    EVIDENCE_INTEGRITY = "evidence_integrity"
    AUDIT_CONTINUITY = "audit_continuity"
    COST_BUDGET = "cost_budget"
    BACKUPS = "backups"
    RELEASE_READINESS = "release_readiness"


@dataclass(frozen=True, slots=True)
class DashboardPanel:
    """A single panel in a dashboard."""
    panel_id: str
    title: str
    query: str
    unit: str
    thresholds: list[tuple[float, str]]  # (value, severity) pairs


@dataclass(frozen=True, slots=True)
class Dashboard:
    """Dashboard configuration."""
    dashboard_id: str
    name: str
    category: DashboardCategory
    description: str
    panels: list[DashboardPanel]
    tags: list[str]

    def to_grafana_json(self) -> dict[str, Any]:
        """Convert to Grafana dashboard JSON format."""
        return {
            "dashboard": {
                "id": self.dashboard_id,
                "title": self.name,
                "tags": self.tags,
                "panels": [
                    {
                        "id": p.panel_id,
                        "title": p.title,
                        "targets": [{"expr": p.query}],
                        "unit": p.unit,
                        "thresholds": p.thresholds,
                    }
                    for p in self.panels
                ],
            },
            "overwrite": True,
        }


def get_dashboards() -> list[Dashboard]:
    """Get all dashboard configurations."""
    return [
        # Service Health Dashboard
        Dashboard(
            dashboard_id="we3-service-health",
            name="WE3 Service Health",
            category=DashboardCategory.SERVICE_HEALTH,
            description="Overall platform health including API availability and throughput",
            panels=[
                DashboardPanel(
                    panel_id="api-availability",
                    title="API Availability (5xx rate)",
                    query=(
                        "1 - (sum(rate(we3_http_responses_total{status=~'5..'}[5m])) / "
                        "sum(rate(we3_http_requests_total[5m]))"
                    ),
                    unit="percent",
                    thresholds=[(99.9, "ok"), (99.5, "warning"), (0, "critical")],
                ),
                DashboardPanel(
                    panel_id="request-rate",
                    title="Requests per Second",
                    query="sum(rate(we3_http_requests_total[5m]))",
                    unit="rps",
                    thresholds=[(0, "ok")],
                ),
                DashboardPanel(
                    panel_id="error-rate",
                    title="Error Rate",
                    query="sum(rate(we3_operation_errors_total[5m])) / sum(rate(we3_operation_count[5m]))",
                    unit="percent",
                    thresholds=[(0, "ok"), (0.01, "warning"), (0.1, "critical")],
                ),
            ],
            tags=["we3", "service", "health"],
        ),
        # Queue Metrics Dashboard
        Dashboard(
            dashboard_id="we3-queue-depth",
            name="WE3 Queue Depth & Age",
            category=DashboardCategory.QUEUE_METRICS,
            description="Job queue depth and age metrics",
            panels=[
                DashboardPanel(
                    panel_id="queue-depth",
                    title="Pending Jobs",
                    query="we3_queue_pending_count",
                    unit="short",
                    thresholds=[(0, "ok"), (100, "warning"), (1000, "critical")],
                ),
                DashboardPanel(
                    panel_id="queue-age",
                    title="Max Queue Age (minutes)",
                    query="max(we3_queue_max_age_seconds) / 60",
                    unit="d",
                    thresholds=[(0, "ok"), (5, "warning"), (30, "critical")],
                ),
                DashboardPanel(
                    panel_id="lease-rate",
                    title="Lease Claims per Second",
                    query="we3_lease_claims_per_second",
                    unit="rps",
                    thresholds=[(0, "ok"), (3, "warning")],
                ),
            ],
            tags=["we3", "queue", "jobs"],
        ),
        # Provider Metrics Dashboard
        Dashboard(
            dashboard_id="we3-provider-errors",
            name="WE3 Provider Errors & Identity",
            category=DashboardCategory.PROVIDER_ERRORS,
            description="Provider latency, errors, and identity consistency",
            panels=[
                DashboardPanel(
                    panel_id="provider-latency",
                    title="Provider Latency (p95 ms)",
                    query="histogram_quantile(0.95, we3_provider_latency_ms)",
                    unit="ms",
                    thresholds=[(0, "ok"), (5000, "warning"), (30000, "critical")],
                ),
                DashboardPanel(
                    panel_id="provider-error-rate",
                    title="Provider Error Rate",
                    query="rate(we3_provider_errors_total[5m])",
                    unit="percent",
                    thresholds=[(0, "ok"), (0.01, "warning"), (0.05, "critical")],
                ),
                DashboardPanel(
                    panel_id="identity-drift",
                    title="Model Identity Drift Events",
                    query="we3_model_identity_drift_total",
                    unit="short",
                    thresholds=[(0, "ok"), (1, "warning"), (10, "critical")],
                ),
            ],
            tags=["we3", "provider", "errors"],
        ),
        # Grading & Review Dashboard
        Dashboard(
            dashboard_id="we3-grading-review",
            name="WE3 Grading & Review Drift",
            category=DashboardCategory.GRADING_REVIEW,
            description="Grading performance and review backlog",
            panels=[
                DashboardPanel(
                    panel_id="grading-latency",
                    title="Grading Duration P95 (seconds)",
                    query="histogram_quantile(0.95, we3_grading_duration_ms) / 1000",
                    unit="s",
                    thresholds=[(0, "ok"), (60, "warning"), (120, "critical")],
                ),
                DashboardPanel(
                    panel_id="review-backlog",
                    title="Unresolved Critical Reviews",
                    query="we3_unresolved_critical_reviews",
                    unit="short",
                    thresholds=[(0, "ok"), (5, "warning"), (10, "critical")],
                ),
                DashboardPanel(
                    panel_id="grader-drift",
                    title="Grader Version Changes",
                    query="we3_grader_version_changes_total",
                    unit="short",
                    thresholds=[(0, "ok"), (1, "warning")],
                ),
            ],
            tags=["we3", "grading", "review"],
        ),
        # Evidence Integrity Dashboard
        Dashboard(
            dashboard_id="we3-evidence-integrity",
            name="WE3 Evidence Integrity",
            category=DashboardCategory.EVIDENCE_INTEGRITY,
            description="Evidence verification and storage metrics",
            panels=[
                DashboardPanel(
                    panel_id="hash-verification",
                    title="Hash Verification Success Rate",
                    query="we3_sli_hash_verification_v1",
                    unit="percent",
                    thresholds=[(1.0, "ok"), (0.99, "warning"), (0.0, "critical")],
                ),
                DashboardPanel(
                    panel_id="artifact-count",
                    title="Total Artifacts Stored",
                    query="we3_artifacts_total",
                    unit="short",
                    thresholds=[(0, "ok")],
                ),
                DashboardPanel(
                    panel_id="storage-bytes",
                    title="Storage Used (GiB)",
                    query="we3_storage_bytes / (1024 * 1024 * 1024)",
                    unit="bytes",
                    thresholds=[(0, "ok"), (100, "warning")],
                ),
            ],
            tags=["we3", "evidence", "integrity"],
        ),
        # Audit Continuity Dashboard
        Dashboard(
            dashboard_id="we3-audit-continuity",
            name="WE3 Audit Continuity",
            category=DashboardCategory.AUDIT_CONTINUITY,
            description="Audit ledger health and event flow",
            panels=[
                DashboardPanel(
                    panel_id="audit-events",
                    title="Audit Events per Hour",
                    query="sum(rate(we3_audit_events_total[1h]))",
                    unit="h",
                    thresholds=[(0, "ok")],
                ),
                DashboardPanel(
                    panel_id="audit-chain-valid",
                    title="Audit Chain Valid",
                    query="we3_audit_chain_valid",
                    unit="bool",
                    thresholds=[(1, "ok"), (0, "critical")],
                ),
                DashboardPanel(
                    panel_id="audit-gap-detection",
                    title="Potential Audit Gaps",
                    query="we3_audit_gaps_detected",
                    unit="short",
                    thresholds=[(0, "ok"), (1, "warning"), (10, "critical")],
                ),
            ],
            tags=["we3", "audit", "continuity"],
        ),
        # Cost & Budget Dashboard
        Dashboard(
            dashboard_id="we3-cost-budget",
            name="WE3 Cost & Budget",
            category=DashboardCategory.COST_BUDGET,
            description="Provider spend and budget utilization",
            panels=[
                DashboardPanel(
                    panel_id="provider-spend",
                    title="Hourly Provider Spend ($)",
                    query="we3_provider_spend_usd",
                    unit="currencyUSD",
                    thresholds=[(0, "ok"), (80, "warning"), (100, "critical")],
                ),
                DashboardPanel(
                    panel_id="grading-spend",
                    title="Hourly Grading Spend ($)",
                    query="we3_grading_spend_usd",
                    unit="currencyUSD",
                    thresholds=[(0, "ok"), (40, "warning"), (50, "critical")],
                ),
                DashboardPanel(
                    panel_id="budget-utilization",
                    title="Budget Utilization %",
                    query="we3_budget_utilization_percent",
                    unit="percent",
                    thresholds=[(0, "ok"), (80, "warning"), (100, "critical")],
                ),
            ],
            tags=["we3", "cost", "budget"],
        ),
        # Backups Dashboard
        Dashboard(
            dashboard_id="we3-backups",
            name="WE3 Backups",
            category=DashboardCategory.BACKUPS,
            description="Backup status, RPO/RTO compliance, and restore readiness",
            panels=[
                DashboardPanel(
                    panel_id="backup-status",
                    title="Last Backup Age (hours)",
                    query="we3_backup_last_age_hours",
                    unit="d",
                    thresholds=[(0, "ok"), (12, "warning"), (24, "critical")],
                ),
                DashboardPanel(
                    panel_id="backup-rpo-compliance",
                    title="RPO Compliance %",
                    query="we3_backup_rpo_compliance_percent",
                    unit="percent",
                    thresholds=[(99.9, "ok"), (95, "warning"), (0, "critical")],
                ),
                DashboardPanel(
                    panel_id="backup-restore-test",
                    title="Last Restore Test (days)",
                    query="we3_backup_last_restore_test_days",
                    unit="d",
                    thresholds=[(0, "ok"), (7, "warning"), (30, "critical")],
                ),
            ],
            tags=["we3", "backups", "dr"],
        ),
        # Release Readiness Dashboard
        Dashboard(
            dashboard_id="we3-release-readiness",
            name="WE3 Release Readiness",
            category=DashboardCategory.RELEASE_READINESS,
            description="Release gate status and dossier verification",
            panels=[
                DashboardPanel(
                    panel_id="gate-status",
                    title="Gate Decisions",
                    query="we3_gate_decisions_total",
                    unit="short",
                    thresholds=[(0, "ok")],
                ),
                DashboardPanel(
                    panel_id="unsafe-compliance",
                    title="Unsafe Compliance Events",
                    query="we3_unsafe_compliance_total",
                    unit="short",
                    thresholds=[(0, "ok"), (1, "critical")],
                ),
                DashboardPanel(
                    panel_id="dossier-verification",
                    title="Dossier Signature Valid",
                    query="we3_dossier_signature_valid",
                    unit="bool",
                    thresholds=[(1, "ok"), (0, "critical")],
                ),
            ],
            tags=["we3", "release", "gates"],
        ),
    ]


__all__ = [
    "DashboardCategory",
    "DashboardPanel",
    "Dashboard",
    "get_dashboards",
]
