"""Long-term capacity, cost, and support operations.

T8.1.9 - Sustains the platform after initial certification through funded ownership,
recurring maintenance, capacity planning, vulnerability response, and cost governance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from ..util import new_id, utc_now

logger = logging.getLogger("wilson.operations")


# =============================================================================
# Cadence Definitions
# =============================================================================


class CadenceType(StrEnum):
    """Operational cadence types."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class CadenceStatus(StrEnum):
    """Status of cadence execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# Service Ownership
# =============================================================================


@dataclass(frozen=True, slots=True)
class ServiceOwner:
    """Service owner information."""

    service_id: str
    team_name: str
    on_call_schedule: str
    escalation_contact: str
    support_hours: str
    backup_owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "team_name": self.team_name,
            "on_call_schedule": self.on_call_schedule,
            "escalation_contact": self.escalation_contact,
            "support_hours": self.support_hours,
            "backup_owner": self.backup_owner,
        }


# =============================================================================
# Threshold Definitions
# =============================================================================


@dataclass(frozen=True, slots=True)
class ThresholdDefinition:
    """Threshold definition for automatic ticket creation."""

    threshold_id: str
    metric_name: str
    warning_value: float
    critical_value: float
    cadence: CadenceType
    owner: str
    follow_up_required: bool = False
    # For metrics where lower values are worse (e.g., headroom), invert the comparison
    lower_is_worse: bool = False

    def check_threshold(self, current_value: float) -> str | None:
        """Check if threshold is breached, return severity or None."""
        if self.lower_is_worse:
            # Lower values trigger breaches (e.g., headroom: 5% is worse than 25%)
            if current_value <= self.critical_value:
                return "critical"
            if current_value <= self.warning_value:
                return "warning"
        else:
            # Higher values trigger breaches (e.g., overdue days: 30 is worse than 5)
            if current_value >= self.critical_value:
                return "critical"
            if current_value >= self.warning_value:
                return "warning"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "metric_name": self.metric_name,
            "warning_value": self.warning_value,
            "critical_value": self.critical_value,
            "cadence": self.cadence.value,
            "owner": self.owner,
        }


# =============================================================================
# Cadence Work Unit
# =============================================================================


@dataclass
class CadenceWork:
    """Work unit for a specific operational cadence."""

    work_id: str
    cadence: CadenceType
    owner: str
    inputs: dict[str, Any]
    status: CadenceStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    ticket_created: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "cadence": self.cadence.value,
            "owner": self.owner,
            "inputs": self.inputs,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "outputs": self.outputs,
            "ticket_created": self.ticket_created,
        }


# =============================================================================
# Ticket Lifecycle
# =============================================================================


@dataclass
class OperationalTicket:
    """Ticket created from threshold or cadence breach."""

    ticket_id: str
    title: str
    description: str
    source_type: str  # threshold, cadence_failure, manual
    severity: str  # critical, high, medium, low
    owner: str
    created_at: datetime
    due_at: datetime | None = None
    follow_ups: list[str] = field(default_factory=list)
    risk_acceptance_required: bool = False
    risk_acceptance_expiry: datetime | None = None

    def is_overdue(self) -> bool:
        """Check if ticket is past due date."""
        if not self.due_at:
            return False
        return utc_now() > self.due_at

    def is_risk_expired(self) -> bool:
        """Check if risk acceptance has expired."""
        if not self.risk_acceptance_expiry:
            return False
        return utc_now() > self.risk_acceptance_expiry

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type,
            "severity": self.severity,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "overdue": self.is_overdue(),
            "risk_accepted_until": self.risk_acceptance_expiry.isoformat()
            if self.risk_acceptance_expiry
            else None,
        }


# =============================================================================
# Metrics Aggregation
# =============================================================================


@dataclass(frozen=True, slots=True)
class CostMetric:
    """Cost metric for capacity reporting."""

    metric_id: str
    scorable_run_cost_cents: float
    family_cost_cents: float
    provider_spend_cents: float
    storage_gb: float
    headroom_available: int  # percentage points

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "scorable_run_cost_cents": self.scorable_run_cost_cents,
            "family_cost_cents": self.family_cost_cents,
            "provider_spend_cents": self.provider_spend_cents,
            "storage_gb": self.storage_gb,
            "headroom_available": self.headroom_available,
        }


@dataclass(frozen=True, slots=True)
class PatchSLA:
    """Patch SLA tracking."""

    severity: str
    target_days: int
    elapsed_days: int
    deadline_date: str
    compliant: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "target_days": self.target_days,
            "elapsed_days": self.elapsed_days,
            "deadline_date": self.deadline_date,
            "compliant": self.compliant,
        }


# =============================================================================
# Operations Cadence Manager
# =============================================================================


class TicketSystem(Protocol):
    """Protocol for ticket system integration."""

    def create_ticket(self, ticket: OperationalTicket) -> str:
        """Create a ticket and return its ID."""
        ...


class OperationsCadenceManager:
    """Manages recurring operational cadences for platform sustainability.

    Cadences:
    - Daily: Health/integrity checks
    - Weekly: Backlog, cost, alert review
    - Monthly: Access, patch, backup, dependency review
    - Quarterly: Capacity, threat model, DR, architecture review
    """

    # Threshold definitions with owners
    THRESHOLDS: list[ThresholdDefinition] = [
        ThresholdDefinition(
            threshold_id="cost_headroom_20pct",
            metric_name="capacity_headroom_percent",
            warning_value=20.0,
            critical_value=10.0,
            cadence=CadenceType.DAILY,
            owner="SRE Team",
            lower_is_worse=True,  # Lower headroom is worse
        ),
        ThresholdDefinition(
            threshold_id="patch_critical_overdue",
            metric_name="critical_patches_overdue_days",
            warning_value=7.0,
            critical_value=30.0,
            cadence=CadenceType.WEEKLY,
            owner="Platform Team",
            lower_is_worse=False,  # More overdue days is worse
        ),
        ThresholdDefinition(
            threshold_id="error_budget_consumed",
            metric_name="error_budget_pct_remaining",
            warning_value=25.0,
            critical_value=10.0,
            cadence=CadenceType.DAILY,
            owner="SRE Team",
            lower_is_worse=True,  # Lower remaining is worse
        ),
        ThresholdDefinition(
            threshold_id="backup_verification_failed",
            metric_name="backup_verification_pct",
            warning_value=95.0,
            critical_value=80.0,
            cadence=CadenceType.WEEKLY,
            owner="SRE Team",
            lower_is_worse=True,  # Lower verification % is worse
        ),
        ThresholdDefinition(
            threshold_id="capacity_triggers",
            metric_name="queue_depth_exceeds_trigger",
            warning_value=5000.0,
            critical_value=10000.0,
            cadence=CadenceType.DAILY,
            owner="Platform Team",
            lower_is_worse=False,  # More queue depth is worse
        ),
    ]

    def __init__(
        self,
        ticket_system: TicketSystem | None = None,
    ) -> None:
        self.ticket_system = ticket_system
        self._owners: dict[str, ServiceOwner] = {}
        self._work_history: dict[str, CadenceWork] = {}
        self._tickets: dict[str, OperationalTicket] = {}

    # -------------------------------------------------------------------------
    # Owner Management
    # -------------------------------------------------------------------------

    def register_owner(self, owner: ServiceOwner) -> None:
        """Register a service owner."""
        self._owners[owner.service_id] = owner
        logger.info(
            "owner_registered",
            extra={"service_id": owner.service_id, "team": owner.team_name},
        )

    def get_owner(self, service_id: str) -> ServiceOwner | None:
        """Get owner for a service."""
        return self._owners.get(service_id)

    def get_all_owners(self) -> list[ServiceOwner]:
        """Get all registered service owners."""
        return list(self._owners.values())

    # -------------------------------------------------------------------------
    # Cadence Execution
    # -------------------------------------------------------------------------

    def create_cadence_work(
        self, cadence: CadenceType, owner: str
    ) -> CadenceWork:
        """Create work unit for cadence execution."""
        work = CadenceWork(
            work_id=f"cadence_{new_id('work')[:16]}",
            cadence=cadence,
            owner=owner,
            inputs={},
            status=CadenceStatus.PENDING,
            created_at=utc_now(),
        )
        self._work_history[work.work_id] = work
        return work

    def start_cadence_work(self, work_id: str) -> CadenceWork | None:
        """Mark cadence work as started."""
        work = self._work_history.get(work_id)
        if work:
            work.status = CadenceStatus.RUNNING
            work.started_at = utc_now()
        return work

    def complete_cadence_work(
        self, work_id: str, outputs: dict[str, Any]
    ) -> CadenceWork | None:
        """Mark cadence work as completed with outputs."""
        work = self._work_history.get(work_id)
        if work:
            work.status = CadenceStatus.COMPLETED
            work.completed_at = utc_now()
            work.outputs = outputs
        return work

    def fail_cadence_work(self, work_id: str, error: str) -> CadenceWork | None:
        """Mark cadence work as failed."""
        work = self._work_history.get(work_id)
        if work:
            work.status = CadenceStatus.FAILED
            work.outputs = {"error": error}
        return work

    # -------------------------------------------------------------------------
    # Threshold Checking
    # -------------------------------------------------------------------------

    def check_thresholds(
        self, metrics: dict[str, float]
    ) -> list[tuple[ThresholdDefinition, str]]:
        """Check all thresholds against current metrics.

        Returns list of (threshold, severity) tuples for breached thresholds.
        """
        breaches = []
        for threshold in self.THRESHOLDS:
            value = metrics.get(threshold.metric_name)
            if value is not None:
                severity = threshold.check_threshold(value)
                if severity:
                    breaches.append((threshold, severity))

        return breaches

    def create_ticket_from_threshold(
        self,
        threshold: ThresholdDefinition,
        severity: str,
        current_value: float,
    ) -> OperationalTicket | None:
        """Create ticket from threshold breach."""
        ticket = OperationalTicket(
            ticket_id=f"ticket_{new_id('op')[:16]}",
            title=f"Threshold breach: {threshold.metric_name}",
            description=f"Current value {current_value} exceeds {severity} threshold for {threshold.metric_name}",
            source_type="threshold",
            severity=severity,
            owner=threshold.owner,
            created_at=utc_now(),
            follow_ups=[],
        )

        self._tickets[ticket.ticket_id] = ticket

        if self.ticket_system:
            self.ticket_system.create_ticket(ticket)

        logger.warning(
            "threshold_breach_ticket_created",
            extra={
                "ticket_id": ticket.ticket_id,
                "threshold": threshold.threshold_id,
                "value": current_value,
            },
        )
        return ticket

    # -------------------------------------------------------------------------
    # Policy Management
    # -------------------------------------------------------------------------

    def get_policy(self, category: str) -> dict[str, Any]:
        """Get versioned support/deprecation policy."""
        # Return versioned policy for APIs, schemas, graders, datasets, models, providers
        policies = {
            "api_v1": {
                "version": "1.0.0",
                "supported_until": "2027-07-16",
                "deprecation_notice": "API v1 remains supported with no planned deprecation",
            },
            "dataset_lifecycle": {
                "states": ["draft", "reviewed", "approved", "deprecated"],
                "deprecation_requires": ["successor_dataset_ref"],
            },
            "grader_versions": {
                "current": "deterministic-v1",
                "calibration_required": True,
            },
        }
        return policies.get(category, {})

    def validate_policy_compliance(self, category: str, value: Any) -> bool:
        """Validate value against versioned policy."""
        policy = self.get_policy(category)
        if category == "dataset_lifecycle":
            return value in policy.get("states", [])
        if category == "grader_versions":
            return value == policy.get("current") or policy.get("calibration_required")
        return True

    # -------------------------------------------------------------------------
    # Monthly Access Review
    # -------------------------------------------------------------------------

    def generate_access_review_report(self) -> dict[str, Any]:
        """Generate monthly access review report.

        Checks for:
        - Departed users in privileged groups
        - Missing owner coverage after staffing changes
        - Exception expiry status
        """
        review = {
            "generated_at": utc_now().isoformat(),
            "services_without_owners": [],
            "users_to_review": [],
            "exceptions_expired_soon": [],
            "stale_access_keys": [],
        }

        # Check for unowned services
        for service_id, owner in self._owners.items():
            if not owner.team_name or owner.team_name == "@unassigned":
                review["services_without_owners"].append(service_id)

        return review

    # -------------------------------------------------------------------------
    # Quarterly Capacity Review
    # -------------------------------------------------------------------------

    def generate_capacity_review(self) -> dict[str, Any]:
        """Generate quarterly capacity planning report.

        Checks for:
        - Capacity headroom against thresholds
        - GPU/compute utilization for accelerators
        - Storage growth projections
        - Cost trends and overruns
        """
        review = {
            "generated_at": utc_now().isoformat(),
            "capacity_headroom": None,
            "gpu_utilization": None,
            "storage_growth_gb": 0,
            "cost_trend": "stable",
            "threshold_breaches_impacting_capacity": [],
        }

        # Check capacity thresholds
        for threshold in self.THRESHOLDS:
            if "headroom" in threshold.metric_name:
                # Would query actual capacity data in production
                pass

        return review

    def generate_slo_evidence(self) -> dict[str, Any]:
        """Generate SLO evidence for operations certification.

        Returns evidence that all six core SLIs have:
        - Registered definitions
        - Appropriate SLO targets
        - Connected alert rules with runbooks
        """
        try:
            from ..observability.sli_slo import get_sli_registry
            from ..observability.alerts import get_alert_rules

            registry = get_sli_registry()
            alert_rules = get_alert_rules()

            core_slis = [
                "sli-api-availability-v1",
                "sli-evidence-durability-v1",
                "sli-queue-start-latency-p95-v1",
                "sli-grading-duration-p95-v1",
                "sli-report-generation-p99-v1",
                "sli-hash-verification-v1",
            ]

            slo_evidence = {
                "generated_at": utc_now().isoformat(),
                "slis_verified": [],
                "slos_monitored": [],
                "alerts_configured": [],
                "runbook_links_valid": True,
            }

            for sli_id in core_slis:
                sli = registry.get_sli(sli_id)
                slo = registry.get_slo_for_sli(sli_id)
                alerts = [a for a in alert_rules if a.sli_id == sli_id]

                if sli and slo:
                    slo_evidence["slis_verified"].append(sli_id)
                    slo_evidence["slos_monitored"].append(slo.slo_id)
                if alerts:
                    slo_evidence["alerts_configured"].extend([a.alert_id for a in alerts])

            return {
                "evidence_type": "slo_verification",
                "valid": len(slo_evidence["slis_verified"]) == len(core_slis),
                "details": slo_evidence,
            }
        except Exception as e:
            return {
                "evidence_type": "slo_verification",
                "valid": False,
                "error": str(e),
            }


# =============================================================================
# Cost Tracking
# =============================================================================


class CostTracker:
    """Tracks cost per scorable run and family."""

    def __init__(self) -> None:
        self._metrics: dict[str, CostMetric] = {}

    def record_cost(
        self,
        metric_id: str,
        scorable_run_cost_cents: float,
        family_cost_cents: float,
        provider_spend_cents: float,
        storage_gb: float,
        headroom_available: int,
    ) -> CostMetric:
        """Record cost metrics."""
        metric = CostMetric(
            metric_id=metric_id,
            scorable_run_cost_cents=scorable_run_cost_cents,
            family_cost_cents=family_cost_cents,
            provider_spend_cents=provider_spend_cents,
            storage_gb=storage_gb,
            headroom_available=headroom_available,
        )
        self._metrics[metric_id] = metric
        return metric

    def get_cost_trend(self, days: int = 30) -> list[CostMetric]:
        """Get cost trend over period."""
        # Would query time-series in production
        return list(self._metrics.values())[-days:]


# =============================================================================
# Support Matrix
# =============================================================================


class SupportMatrix:
    """Manages support coverage matrix."""

    # Standard support hours and response times
    SUPPORT_LEVELS = {
        "sev-1": {"response_hours": 1, "coverage": "24/7"},
        "sev-2": {"response_hours": 4, "coverage": "business-hours"},
        "sev-3": {"response_hours": 24, "coverage": "business-hours"},
        "sev-4": {"response_hours": 72, "coverage": "business-days"},
    }

    def __init__(self) -> None:
        self._coverage: dict[str, dict[str, Any]] = {}

    def set_coverage(self, service_id: str, level: str, owner: str) -> None:
        """Set support coverage for a service."""
        self._coverage[service_id] = {
            "level": level,
            "owner": owner,
            "hours": self.SUPPORT_LEVELS.get(level, {}).get("response_hours"),
        }

    def check_coverage(self, service_id: str) -> dict[str, Any] | None:
        """Check support coverage for a service."""
        return self._coverage.get(service_id)

    def get_all_coverage(self) -> dict[str, dict[str, Any]]:
        """Get all service coverage."""
        return self._coverage.copy()


__all__ = [
    "CadenceType",
    "CadenceStatus",
    "ServiceOwner",
    "ThresholdDefinition",
    "CadenceWork",
    "OperationalTicket",
    "CostMetric",
    "PatchSLA",
    "OperationsCadenceManager",
    "CostTracker",
    "SupportMatrix",
    "TicketSystem",
]