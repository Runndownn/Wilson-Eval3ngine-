"""
Error Budget Policy and Release Decision Framework.

TODO 52 - T8.1.2: Error budget policy and release consequences
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any


class ErrorBudgetState(StrEnum):
    """State of the error budget."""
    OK = "ok"  # Within budget
    WARNING = "warning"  # Approaching burn
    BREACHED = "breached"  # Burn rate exceeded
    EXHAUSTED = "exhausted"  # No budget remaining


@dataclass(frozen=True, slots=True)
class ErrorBudget:
    """Error budget configuration for SLOs."""
    slo_id: str
    budget_percent: float  # Percentage of allowable errors (e.g., 0.1% for 99.9% SLO)
    window_days: int  # Measurement window in days
    burn_rate_threshold: float = 1.0  # Multiplier for fast burn detection
    frozen: bool = False  # Whether budget is frozen (maintenance window)

    def compute_budget_allowance(self, total_requests: int) -> int:
        """Compute number of allowed errors in window."""
        return int(total_requests * self.budget_percent / 100)

    def compute_burn_rate(
        self,
        errors_in_window: int,
        total_in_window: int,
    ) -> float:
        """Compute error burn rate relative to budget."""
        if total_in_window == 0:
            return 0.0
        actual_error_rate = errors_in_window / total_in_window
        budget_error_rate = self.budget_percent / 100
        return actual_error_rate / budget_error_rate if budget_error_rate > 0 else 0.0


@dataclass
class ErrorBudgetStatus:
    """Current state of error budget for an SLO."""
    slo_id: str
    budget: ErrorBudget
    errors_in_window: int
    total_in_window: int
    burn_rate: float
    state: ErrorBudgetState
    remaining_budget: float  # Percentage remaining
    next_evaluation: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "budget_percent": self.budget.budget_percent,
            "burn_rate": round(self.burn_rate, 2),
            "state": self.state.value,
            "remaining_budget": round(self.remaining_budget, 2),
            "errors_in_window": self.errors_in_window,
            "total_in_window": self.total_in_window,
        }


class ErrorBudgetPolicy:
    """
    Error budget policy engine.

    Enforces release consequences based on error budget state.
    """

    # Default SLO budgets
    DEFAULT_BUDGETS: dict[str, ErrorBudget] = {
        "slo-api-availability-99.9": ErrorBudget(
            slo_id="slo-api-availability-99.9",
            budget_percent=0.1,  # 0.1% error budget for 99.9% SLO
            window_days=30,
            burn_rate_threshold=2.0,  # Alert on 2x burn rate
        ),
        "slo-evidence-durability-99.99": ErrorBudget(
            slo_id="slo-evidence-durability-99.99",
            budget_percent=0.01,  # 0.01% for 99.99% SLO
            window_days=90,
            burn_rate_threshold=3.0,
        ),
    }

    # Release consequences
    CONSEQUENCES: dict[ErrorBudgetState, str] = {
        ErrorBudgetState.OK: "releases_allowed",
        ErrorBudgetState.WARNING: "releases_allowed_with_approval",
        ErrorBudgetState.BREACHED: "feature_freeze_required",
        ErrorBudgetState.EXHAUSTED: "release_blocked",
    }

    def __init__(self) -> None:
        self.budgets: dict[str, ErrorBudget] = dict(self.DEFAULT_BUDGETS)

    def evaluate_budget(
        self,
        slo_id: str,
        errors_in_window: int,
        total_in_window: int,
    ) -> ErrorBudgetStatus:
        """Evaluate error budget status for an SLO."""
        budget = self.budgets.get(slo_id)
        if not budget:
            raise ValueError(f"Unknown SLO: {slo_id}")

        burn_rate = budget.compute_burn_rate(errors_in_window, total_in_window)

        if burn_rate >= 2.0:
            state = ErrorBudgetState.EXHAUSTED
        elif burn_rate >= 1.0:
            state = ErrorBudgetState.BREACHED
        elif burn_rate >= budget.burn_rate_threshold:
            state = ErrorBudgetState.WARNING
        else:
            state = ErrorBudgetState.OK

        remaining = max(0, 100 - (burn_rate * 100))

        return ErrorBudgetStatus(
            slo_id=slo_id,
            budget=budget,
            errors_in_window=errors_in_window,
            total_in_window=total_in_window,
            burn_rate=burn_rate,
            state=state,
            remaining_budget=remaining,
            next_evaluation=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    def get_release_policy(
        self,
        budget_statuses: list[ErrorBudgetStatus],
    ) -> tuple[str, list[str]]:
        """Get release policy and required approvals."""
        worst_state = ErrorBudgetState.OK
        for status in budget_statuses:
            if status.state.value > worst_state.value:
                worst_state = status.state

        policy = self.CONSEQUENCES.get(worst_state, "unknown")

        required_approvals: list[str] = []
        if worst_state == ErrorBudgetState.WARNING:
            required_approvals.append("platform_lead_approval")
        elif worst_state == ErrorBudgetState.BREACHED:
            required_approvals.extend([
                "platform_lead_approval",
                "sre_lead_approval",
            ])
        elif worst_state == ErrorBudgetState.EXHAUSTED:
            required_approvals.extend([
                "platform_lead_approval",
                "sre_lead_approval",
                "executive_approval",
            ])

        return policy, required_approvals

    def require_maintenance_window(
        self,
        budget_statuses: list[ErrorBudgetState],
    ) -> bool:
        """Check if maintenance window is required."""
        # Freeze features if any budget is breached or exhausted
        return any(
            s in (ErrorBudgetState.BREACHED, ErrorBudgetState.EXHAUSTED)
            for s in budget_statuses
        )

    def get_maintenance_freeze(self) -> dict[str, Any]:
        """Get maintenance window configuration."""
        return {
            "freeze_start": datetime.now(timezone.utc).isoformat(),
            "freeze_duration_hours": 24,
            "required_actions": [
                "investigate_root_cause",
                "implement_fix",
                "validate_recovery",
                "get_approval_before_unfreeze",
            ],
        }


def evaluate_all_budgets(
    error_counts: dict[str, int],
    total_counts: dict[str, int],
) -> list[ErrorBudgetStatus]:
    """Evaluate all SLO budgets in one pass."""
    policy = ErrorBudgetPolicy()
    statuses = []

    for slo_id in policy.budgets:
        errors = error_counts.get(slo_id, 0)
        total = total_counts.get(slo_id, 0)
        status = policy.evaluate_budget(slo_id, errors, total)
        statuses.append(status)

    return statuses


@dataclass
class DegradationStatus:
    """Status of graceful degradation controls."""
    admission_paused: bool = False
    read_only_mode: bool = False
    certification_blocked: bool = False
    reasons: list[str] = field(default_factory=list)


class GracefulDegradationController:
    """
    Controller for graceful degradation rules.

    Implements:
    - Admission pause when integrity uncertain
    - Read-only mode for safe report access
    - Certification restrictions
    """

    # Thresholds from runbook
    EVIDENCE_INTEGRITY_THRESHOLD = 0.99
    CRITICAL_REVIEW_BACKLOG_THRESHOLD = 50
    HASH_VERIFICATION_FAILURE_HOURS = 1

    def __init__(self) -> None:
        self._metrics: dict[str, float] = {}

    def check_admission_pause(
        self,
        evidence_durability: float | None = None,
        critical_review_backlog: int = 0,
        hash_verification_failing_hours: float = 0,
    ) -> DegradationStatus:
        """Check if experiment admission should be paused."""
        status = DegradationStatus()

        if evidence_durability is not None:
            if evidence_durability < self.EVIDENCE_INTEGRITY_THRESHOLD:
                status.admission_paused = True
                status.reasons.append(
                    f"Evidence durability {evidence_durability:.4f} below threshold {self.EVIDENCE_INTEGRITY_THRESHOLD}"
                )

        if critical_review_backlog > self.CRITICAL_REVIEW_BACKLOG_THRESHOLD:
            status.admission_paused = True
            status.reasons.append(
                f"Critical review backlog {critical_review_backlog} "
                f"exceeds threshold {self.CRITICAL_REVIEW_BACKLOG_THRESHOLD}"
            )

        if hash_verification_failing_hours >= self.HASH_VERIFICATION_FAILURE_HOURS:
            status.admission_paused = True
            status.reasons.append(
                f"Hash verification failing for {hash_verification_failing_hours} hours"
            )

        return status

    def check_read_only_mode(
        self,
        db_writes_failing: bool = False,
        evidence_integrity_verified: bool = False,
    ) -> DegradationStatus:
        """Check if read-only mode should be enabled."""
        status = DegradationStatus()

        if db_writes_failing and evidence_integrity_verified:
            status.read_only_mode = True
            status.reasons.append("Database writes unavailable but evidence verified")

        return status

    def check_certification(
        self,
        missing_evidence: bool = False,
        unresolved_critical_reviews: bool = False,
        model_identity_drift: bool = False,
        audit_chain_failed: bool = False,
    ) -> DegradationStatus:
        """Check if certification should be blocked."""
        status = DegradationStatus()

        status.certification_blocked = any([
            missing_evidence,
            unresolved_critical_reviews,
            model_identity_drift,
            audit_chain_failed,
        ])

        if missing_evidence:
            status.reasons.append("Missing evidence for completed runs")
        if unresolved_critical_reviews:
            status.reasons.append("Unresolved critical reviews present")
        if model_identity_drift:
            status.reasons.append("Model identity drift detected")
        if audit_chain_failed:
            status.reasons.append("Audit chain continuity failed")

        return status

    def evaluate_all(
        self,
        evidence_durability: float | None = None,
        critical_review_backlog: int = 0,
        hash_verification_failing_hours: float = 0,
        db_writes_failing: bool = False,
        evidence_integrity_verified: bool = False,
        missing_evidence: bool = False,
        unresolved_critical_reviews: bool = False,
        model_identity_drift: bool = False,
        audit_chain_failed: bool = False,
    ) -> DegradationStatus:
        """Evaluate all graceful degradation conditions."""
        admission = self.check_admission_pause(
            evidence_durability, critical_review_backlog, hash_verification_failing_hours
        )
        readonly = self.check_read_only_mode(
            db_writes_failing, evidence_integrity_verified
        )
        cert = self.check_certification(
            missing_evidence, unresolved_critical_reviews,
            model_identity_drift, audit_chain_failed,
        )

        return DegradationStatus(
            admission_paused=admission.admission_paused,
            read_only_mode=readonly.read_only_mode,
            certification_blocked=cert.certification_blocked,
            reasons=admission.reasons + readonly.reasons + cert.reasons,
        )

    def is_system_degraded(self, status: DegradationStatus) -> bool:
        """Check if system is in any degraded state."""
        return status.admission_paused or status.read_only_mode or status.certification_blocked

    def get_degradation_summary(self, status: DegradationStatus) -> dict[str, Any]:
        """Get summary of degradation state for operators.

        Security: Returns no sensitive data, only operational status.
        """
        return {
            "admission_paused": status.admission_paused,
            "read_only_mode": status.read_only_mode,
            "certification_blocked": status.certification_blocked,
            "reason_count": len(status.reasons),
            "degraded": self.is_system_degraded(status),
        }


__all__ = [
    "ErrorBudgetState",
    "ErrorBudget",
    "ErrorBudgetStatus",
    "ErrorBudgetPolicy",
    "evaluate_all_budgets",
    "GracefulDegradationController",
    "DegradationStatus",
]
