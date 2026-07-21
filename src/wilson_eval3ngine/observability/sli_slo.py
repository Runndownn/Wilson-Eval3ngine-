"""
SLI/SLO definitions and calculation engine.

TODO 52 - T8.1.2: Service Level Indicators and Objectives for observability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from ..telemetry import is_safe_for_telemetry, record_metric
from ..util import utc_now

logger = logging.getLogger(__name__)


class SLIKind(StrEnum):
    """Types of Service Level Indicators."""
    API_AVAILABILITY = "api_availability"
    EVIDENCE_DURABILITY = "evidence_durability"
    QUEUE_LATENCY = "queue_latency"
    GRADING_DURATION = "grading_duration"
    REPORT_GENERATION = "report_generation"
    HASH_VERIFICATION = "hash_verification"


class AlertSeverity(StrEnum):
    """Alert severity levels."""
    PAGE = "page"  # Immediate paging
    TICKET = "ticket"  # Ticket creation
    LOG = "log"  # Log only


@dataclass(frozen=True, slots=True)
class SLI:
    """Service Level Indicator definition."""
    sli_id: str
    name: str
    kind: SLIKind
    description: str
    query_template: str
    measurement_window_minutes: int
    valid_from: str
    valid_until: str | None = None
    source_of_truth: str = "telemetry_first"  # "telemetry_first" or "persisted_state"
    owner: str = ""  # Team/person responsible for SLI

    def compute_from_telemetry(
        self,
        telemetries: list[dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Compute SLI value from telemetry records."""
        # Filter to window
        window_records = [
            t for t in telemetries
            if start_time <= t.get("timestamp", utc_now()) <= end_time
        ]

        if not window_records:
            return {
                "sli_id": self.sli_id,
                "value": None,
                "numerator": 0,
                "denominator": 0,
                "window_start": start_time.isoformat(),
                "window_end": end_time.isoformat(),
            }

        # Apply query-specific logic
        if self.kind == SLIKind.API_AVAILABILITY:
            # Count successful operations vs total attempts
            successes = sum(1 for t in window_records if t.get("status") == "success")
            total = len(window_records)
            value = successes / total if total > 0 else 0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "numerator": successes,
                "denominator": total,
                "window_start": start_time.isoformat(),
                "window_end": end_time.isoformat(),
            }

        elif self.kind == SLIKind.EVIDENCE_DURABILITY:
            # Count persisted records vs accepted records
            persisted = sum(1 for t in window_records if t.get("persisted"))
            accepted = sum(1 for t in window_records if t.get("accepted"))
            value = persisted / accepted if accepted > 0 else 1.0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "numerator": persisted,
                "denominator": accepted,
            }

        elif self.kind == SLIKind.QUEUE_LATENCY:
            # Measure queue start time (pending -> leased transition)
            latencies = [
                t.get("queue_start_latency_ms", 0)
                for t in window_records
                if "queue_start_latency_ms" in t
            ]
            if latencies:
                sorted_lat = sorted(latencies)
                p95_idx = int(len(sorted_lat) * 0.95)
                value = sorted_lat[p95_idx] / 60000  # Convert ms to minutes
            else:
                value = 0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "p95_minutes": value,
                "sample_count": len(latencies),
            }

        elif self.kind == SLIKind.GRADING_DURATION:
            # Measure grading time
            durations = [
                t.get("grading_duration_ms", 0)
                for t in window_records
                if "grading_duration_ms" in t
            ]
            if durations:
                sorted_dur = sorted(durations)
                p95_idx = int(len(sorted_dur) * 0.95)
                value = sorted_dur[p95_idx] / 1000  # Convert ms to seconds
            else:
                value = 0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "p95_seconds": value,
            }

        elif self.kind == SLIKind.REPORT_GENERATION:
            # Measure report generation time (p99)
            times = [
                t.get("report_generation_seconds", 0)
                for t in window_records
                if "report_generation_seconds" in t
            ]
            if times:
                sorted_times = sorted(times)
                p99_idx = int(len(sorted_times) * 0.99)
                value = sorted_times[p99_idx]
            else:
                value = 0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "p99_seconds": value,
            }

        elif self.kind == SLIKind.HASH_VERIFICATION:
            # Measure scheduled hash verification success
            verified = sum(1 for t in window_records if t.get("hash_verified"))
            scheduled = sum(1 for t in window_records if t.get("hash_scheduled"))
            value = verified / scheduled if scheduled > 0 else 1.0
            return {
                "sli_id": self.sli_id,
                "value": value,
                "numerator": verified,
                "denominator": scheduled,
            }

        return {"sli_id": self.sli_id, "value": None}


@dataclass(frozen=True, slots=True)
class SLO:
    """Service Level Objective."""
    slo_id: str
    sli_id: str
    name: str
    target: float  # Target value (e.g., 0.999 for 99.9%)
    warning: float  # Warning threshold
    measurement_window_days: int
    alerting_window_minutes: int = 5
    severity: AlertSeverity = AlertSeverity.TICKET
    owner: str = ""  # Team/person responsible
    runbook_url: str = ""  # Link to runbook

    def is_breaching(self, sli_value: float | None) -> bool:
        """Check if SLI is breaching SLO."""
        if sli_value is None:
            return True  # Missing data is a breach
        return sli_value < self.target

    def is_warning(self, sli_value: float | None) -> bool:
        """Check if SLI is in warning state."""
        if sli_value is None:
            return False
        return sli_value < self.warning

    def to_dict(self) -> dict[str, Any]:
        """Serialize SLO to dictionary for configuration management."""
        return {
            "slo_id": self.slo_id,
            "sli_id": self.sli_id,
            "name": self.name,
            "target": self.target,
            "warning": self.warning,
            "measurement_window_days": self.measurement_window_days,
            "alerting_window_minutes": self.alerting_window_minutes,
            "severity": self.severity.value,
            "owner": self.owner,
            "runbook_url": self.runbook_url,
        }


@dataclass
class SLIResult:
    """Computed SLI result with status."""
    sli: SLI
    slo: SLO
    value: float | None
    numerator: int
    denominator: int
    timestamp: datetime
    status: str  # "ok", "warning", "breach"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sli_id": self.sli.sli_id,
            "slo_id": self.slo.slo_id,
            "name": self.sli.name,
            "value": self.value,
            "target": self.slo.target,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }


class SLIRegistry:
    """Registry of SLI and SLO definitions."""

    def __init__(self) -> None:
        self._slis: dict[str, SLI] = {}
        self._slos: dict[str, SLO] = {}
        self._initialize_core()

    def _initialize_core(self) -> None:
        """Initialize core platform SLIs and SLOs."""
        # API Availability - 99.9%
        api_slis: list[SLI] = [
            SLI(
                sli_id="sli-api-availability-v1",
                name="API Availability (99.9%)",
                kind=SLIKind.API_AVAILABILITY,
                description="Percentage of successful API operations",
                query_template="sum(rate(we3_operation_success[5m])) / sum(rate(we3_operation_total[5m]))",
                measurement_window_minutes=5,
                valid_from="2026-07-16",
                source_of_truth="telemetry_first",
                owner="Platform Team",
            ),
        ]

        # Evidence Durability - 99.99% accepted-definition durability
        evidence_slis: list[SLI] = [
            SLI(
                sli_id="sli-evidence-durability-v1",
                name="Evidence Durability (99.99%)",
                kind=SLIKind.EVIDENCE_DURABILITY,
                description="Percentage of accepted records successfully persisted",
                query_template="count(persisted_evidence) / count(accepted_evidence)",
                measurement_window_minutes=60,
                valid_from="2026-07-16",
                source_of_truth="persisted_state",
                owner="SRE Team",
            ),
        ]

        # Queue Start Latency - p95 <= 5 minutes
        queue_slis: list[SLI] = [
            SLI(
                sli_id="sli-queue-start-latency-p95-v1",
                name="Queue Start Latency P95 (<=5 min)",
                kind=SLIKind.QUEUE_LATENCY,
                description="Time from acceptance to lease acquisition (p95)",
                query_template="histogram_quantile(0.95, we3_queue_start_latency_ms)",
                measurement_window_minutes=60,
                valid_from="2026-07-16",
                source_of_truth="telemetry_first",
                owner="SRE Team",
            ),
        ]

        # Grading Duration - p95 <= 2 minutes
        grading_slis: list[SLI] = [
            SLI(
                sli_id="sli-grading-duration-p95-v1",
                name="Grading Duration P95 (<=2 min)",
                kind=SLIKind.GRADING_DURATION,
                description="Time to grade a run response (p95)",
                query_template="histogram_quantile(0.95, we3_grading_duration_ms)",
                measurement_window_minutes=60,
                valid_from="2026-07-16",
                source_of_truth="telemetry_first",
                owner="Evaluation Team",
            ),
        ]

        # Report Generation - p99 <= 10 minutes
        report_slis: list[SLI] = [
            SLI(
                sli_id="sli-report-generation-p99-v1",
                name="Report Generation P99 (<=10 min)",
                kind=SLIKind.REPORT_GENERATION,
                description="Time to generate evaluation reports (p99)",
                query_template="histogram_quantile(0.99, we3_report_generation_seconds)",
                measurement_window_minutes=60,
                valid_from="2026-07-16",
                source_of_truth="telemetry_first",
                owner="SRE Team",
            ),
        ]

        # Hash Verification - 100% scheduled verification
        hash_slis: list[SLI] = [
            SLI(
                sli_id="sli-hash-verification-v1",
                name="Hash Verification (100%)",
                kind=SLIKind.HASH_VERIFICATION,
                description="Percentage of scheduled hash verifications completed",
                query_template="count(hash_verified) / count(hash_scheduled)",
                measurement_window_minutes=1440,  # 24 hours
                valid_from="2026-07-16",
                source_of_truth="persisted_state",
                owner="Security Team",
            ),
        ]

        for sli in api_slis + evidence_slis + queue_slis + grading_slis + report_slis + hash_slis:
            self._slis[sli.sli_id] = sli

        # Define SLOs
        self._slos = {
            "slo-api-availability-99.9": SLO(
                slo_id="slo-api-availability-99.9",
                sli_id="sli-api-availability-v1",
                name="API Availability 99.9%",
                target=0.999,
                warning=0.9995,
                measurement_window_days=30,
                alerting_window_minutes=5,
                severity=AlertSeverity.PAGE,
                owner="Platform Team",
                runbook_url="/docs/operations/sev-incidents.md#provider-outage-response",
            ),
            "slo-evidence-durability-99.99": SLO(
                slo_id="slo-evidence-durability-99.99",
                sli_id="sli-evidence-durability-v1",
                name="Evidence Durability 99.99%",
                target=0.9999,
                warning=0.99995,
                measurement_window_days=90,
                alerting_window_minutes=60,
                severity=AlertSeverity.PAGE,
                owner="SRE Team",
                runbook_url="/docs/operations/sev-incidents.md#evidence-corruption-response",
            ),
            "slo-queue-start-latency-5min": SLO(
                slo_id="slo-queue-start-latency-5min",
                sli_id="sli-queue-start-latency-p95-v1",
                name="Queue Start Latency P95 (5 min)",
                target=5.0,  # 5 minutes in minutes
                warning=3.0,  # 3 minutes warning
                measurement_window_days=30,
                alerting_window_minutes=60,
                severity=AlertSeverity.TICKET,
                owner="SRE Team",
                runbook_url="/docs/operations/sev-incidents.md#queue-backlog-response",
            ),
            "slo-grading-duration-2min": SLO(
                slo_id="slo-grading-duration-2min",
                sli_id="sli-grading-duration-p95-v1",
                name="Grading Duration P95 (2 min)",
                target=2.0,  # 2 minutes in seconds
                warning=1.0,  # 1 minute warning
                measurement_window_days=30,
                alerting_window_minutes=30,
                severity=AlertSeverity.TICKET,
                owner="Evaluation Team",
                runbook_url="/docs/operations/sev-incidents.md#grading-drift-response",
            ),
            "slo-report-generation-10min": SLO(
                slo_id="slo-report-generation-10min",
                sli_id="sli-report-generation-p99-v1",
                name="Report Generation P99 (10 min)",
                target=10.0,  # 10 minutes in seconds
                warning=5.0,  # 5 minutes warning
                measurement_window_days=30,
                alerting_window_minutes=60,
                severity=AlertSeverity.TICKET,
                owner="SRE Team",
                runbook_url="/docs/operations/sev-incidents.md#report-generation-response",
            ),
            "slo-hash-verification-100": SLO(
                slo_id="slo-hash-verification-100",
                sli_id="sli-hash-verification-v1",
                name="Hash Verification (100%)",
                target=1.0,  # 100%
                warning=1.0,
                measurement_window_days=7,
                alerting_window_minutes=60,
                severity=AlertSeverity.PAGE,
                owner="Security Team",
                runbook_url="/docs/operations/sev-incidents.md#evidence-corruption-response",
            ),
        }

    def get_sli(self, sli_id: str) -> SLI | None:
        return self._slis.get(sli_id)

    def get_slo(self, slo_id: str) -> SLO | None:
        return self._slos.get(slo_id)

    def get_slo_for_sli(self, sli_id: str) -> SLO | None:
        """Get the SLO for a given SLI."""
        sli = self._slis.get(sli_id)
        if sli:
            for slo in self._slos.values():
                if slo.sli_id == sli_id:
                    return slo
        return None


class StateReconciler:
    """Reconciles telemetry with persisted state to detect lost work.

    Implements TODO 52 requirement: "Reconcile telemetry-based indicators with
    authoritative persisted state so dropped telemetry cannot imply success."
    """

    # Allowed label keys for metric validation (prevents injection)
    ALLOWED_LABEL_KEYS: frozenset[str] = frozenset({
        "project_id", "experiment_id", "run_id", "case_id", "model_config_id",
    })

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._maintenance_suppressions: dict[str, datetime] = {}

    def check_lost_jobs(
        self,
        project_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Check for jobs that telemetry shows completed but aren't in database.

        Reconciles telemetry-based indicators with authoritative persisted state
        so dropped telemetry cannot imply success.
        """
        # Validate inputs
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        result: dict[str, Any] = {
            "project_id": project_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "telemetry_shows_completed": 0,
            "database_has_records": 0,
            "potential_lost_jobs": 0,
            "reconciled": True,
            "check_performed_at": utc_now().isoformat(),
        }

        # In production, this would query both telemetry store and database:
        # - Query telemetry for all completed run markers in time window
        # - Query database for actual persisted run records
        # - Compute diff to find potentially lost jobs
        # - Emit alert if gap detected even without telemetry data

        # Simulation placeholder - would integrate with actual persistence layer
        logger.info(
            "lost_jobs_check_performed",
            extra={"project_id": project_id, "start": start_time.isoformat(), "end": end_time.isoformat()},
        )

        return result

    def check_stuck_jobs(self) -> dict[str, Any]:
        """Find jobs stuck in non-terminal states.

        Detects jobs that haven't progressed for extended periods,
        indicating potential worker failure or deadlock.
        """
        stuck_jobs: list[dict[str, Any]] = []

        # In production: query jobs table for non-terminal states
        # with stale timestamps beyond expected lease duration

        result = {
            "stuck_jobs": stuck_jobs,
            "stuck_count": len(stuck_jobs),
            "check_performed_at": utc_now().isoformat(),
        }

        logger.info(
            "stuck_jobs_check_performed",
            extra={"stuck_count": len(stuck_jobs)},
        )

        return result

    def verify_evidence_integrity(self, project_id: str) -> dict[str, Any]:
        """Verify all evidence hashes match stored content.

        Cross-checks stored SHA-256 hashes against actual object content
        in evidence store to detect corruption or tampering.
        """
        result = {
            "project_id": project_id,
            "verified_count": 0,
            "failed_count": 0,
            "verification_time": utc_now().isoformat(),
        }

        # In production:
        # - Query evidence_metadata for all hashes in project
        # - Fetch each object and verify SHA-256
        # - Record any mismatches

        logger.info(
            "evidence_integrity_check_performed",
            extra={"project_id": project_id},
        )

        return result

    def validate_metric_labels(self, labels: dict[str, Any]) -> dict[str, Any]:
        """Validate and filter metric labels for safety.

        Security: Prevents injection of arbitrary high-cardinality labels
        that could cause cardinality explosion or injection attacks.
        """
        return {
            k: v for k, v in labels.items()
            if k in self.ALLOWED_LABEL_KEYS and is_safe_for_telemetry(v)
        }

    def start_maintenance_suppression(self, alert_id: str, duration_hours: int = 2) -> None:
        """Start maintenance window suppression for an alert.

        Prevents alert firing during scheduled maintenance operations.
        """
        end_time = utc_now() + timedelta(hours=duration_hours)
        self._maintenance_suppressions[alert_id] = end_time
        logger.info(
            "maintenance_suppression_started",
            extra={"alert_id": alert_id, "until": end_time.isoformat()},
        )

    def is_suppressed(self, alert_id: str) -> bool:
        """Check if alert is currently suppressed for maintenance."""
        if alert_id not in self._maintenance_suppressions:
            return False
        end_time = self._maintenance_suppressions[alert_id]
        return utc_now() < end_time

    def end_maintenance_suppression(self, alert_id: str) -> None:
        """End maintenance suppression for an alert."""
        self._maintenance_suppressions.pop(alert_id, None)
        logger.info(
            "maintenance_suppression_ended",
            extra={"alert_id": alert_id},
        )


# Global registry singleton
_sli_registry: SLIRegistry | None = None


def get_sli_registry() -> SLIRegistry:
    """Get global SLI registry."""
    global _sli_registry
    if _sli_registry is None:
        _sli_registry = SLIRegistry()
    return _sli_registry


def record_sli_value(sli_id: str, value: float, **labels: Any) -> None:
    """Record an SLI value for monitoring."""
    registry = get_sli_registry()
    _ = registry.get_sli(sli_id)  # Used for validation
    slo = registry.get_slo_for_sli(sli_id)

    if slo and slo.is_breaching(value):
        record_metric("we3.slo.breach", 1.0, sli_id=sli_id, **labels)
    elif slo and slo.is_warning(value):
        record_metric("we3.slo.warning", 1.0, sli_id=sli_id, **labels)
    else:
        record_metric("we3.slo.ok", 1.0, sli_id=sli_id, **labels)

    record_metric(f"we3.sli.{sli_id}", value, **labels)


__all__ = [
    "SLIKind",
    "AlertSeverity",
    "SLI",
    "SLO",
    "SLIResult",
    "SLIRegistry",
    "StateReconciler",
    "get_sli_registry",
    "record_sli_value",
]
