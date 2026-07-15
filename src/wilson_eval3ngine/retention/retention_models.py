# Systems: Retention Lifecycle Management
# Tags: RETENTION
# Colors: Slate
# Provenance: Authored here
# Tag confidence: High
# Inventory date: 2026-07-15

"""Retention state matrix for garbage collection safety and policy enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetentionLifeCycleState(StrEnum):
    """Canonical retention states across the corpus lifecycle."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    DELETED_OCCURRENCE = "deleted_occurrence"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"
    HELD = "held"
    AUDIT_LINKED = "audit_linked"
    RECOVERABLE = "recoverable"
    ELIGIBLE_FOR_DESTRUCTION = "eligible_for_destruction"


class HoldType(StrEnum):
    """Types of holds that can prevent garbage collection."""

    LEGAL = "legal"
    POLICY = "policy"
    MIGRATION = "migration"
    ROLLBACK = "rollback"


class ProposedAction(StrEnum):
    """Actions proposed by retention evaluation."""

    DELETE = "delete"
    ARCHIVE = "archive"
    QUARANTINE = "quarantine"
    NONE = "none"


class RetentionRule(BaseModel):
    """Retention policy configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    policy_version: str = Field(min_length=1)
    raw_content_policy: Literal["retain-restricted", "retain-governed", "discard-after-compile"]
    derivative_policy: Literal["retain", "retain-reviewed-only", "ephemeral"]
    legal_hold: bool = False
    review_expiry_days: int | None = Field(default=None, ge=1)

    @field_validator("policy_version")
    @classmethod
    def _normalize_policy_version(cls, value: str) -> str:
        return value.strip()


class RetentionHold(BaseModel):
    """Hold record that can block deletion."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    hold_type: HoldType
    reason: str = Field(min_length=1)
    applied_at: datetime
    correlation_id: str
    expires_at: datetime | None = None

    @field_validator("reason", "correlation_id")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return value.strip()


class ReferenceMap(BaseModel):
    """Map of references that prevent deletion."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    canonical: list[str] = Field(default_factory=list)
    projected: list[str] = Field(default_factory=list)
    audit: list[str] = Field(default_factory=list)
    migration: list[str] = Field(default_factory=list)
    rollback: list[str] = Field(default_factory=list)
    cluster: list[str] = Field(default_factory=list)
    tombstone: list[str] = Field(default_factory=list)
    outbox_event: list[str] = Field(default_factory=list)
    cursor: list[str] = Field(default_factory=list)
    disposable_projection: list[str] = Field(default_factory=list)

    def total_reference_count(self) -> int:
        return (
            len(self.canonical)
            + len(self.projected)
            + len(self.audit)
            + len(self.migration)
            + len(self.rollback)
            + len(self.cluster)
            + len(self.tombstone)
            + len(self.outbox_event)
            + len(self.cursor)
            + len(self.disposable_projection)
        )


class SafetyStatus(BaseModel):
    """Safety evaluation status for potential deletion."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    deletion_safe: bool = False
    reference_count: int = Field(default=0, ge=0)
    hold_count: int = Field(default=0, ge=0)
    audit_preserved: bool = True


class RetentionStateMatrix(BaseModel):
    """Complete retention state matrix for an object."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = "retention_state_matrix.v1"
    object_id: str = Field(pattern=r"^rudi-k:[a-f0-9]{24}$")
    scope: str = Field(min_length=1)
    retention_rule: RetentionRule
    lifecycle_state: RetentionLifeCycleState | None = None
    holds: list[RetentionHold] = Field(default_factory=list)
    references: ReferenceMap = Field(default_factory=ReferenceMap)
    proposed_action: ProposedAction = ProposedAction.NONE
    approval: dict[str, Any] | None = None
    safety_status: SafetyStatus | None = None
    evidence_refs: list[dict[str, str]] | None = None

    @field_validator("object_id", "scope")
    @classmethod
    def _normalize_fields(cls, value: str) -> str:
        return value.strip()

    def evaluate_deletion_safety(
        self,
        *,
        grace_period_hours: int = 24,
        now: datetime | None = None,
    ) -> SafetyStatus:
        """Evaluate whether the object can be safely deleted."""
        now_val = now or datetime.now(tz=UTC)

        hold_count = sum(
            1
            for hold in self.holds
            if hold.expires_at is None or hold.expires_at > now_val
        )
        reference_count = self.references.total_reference_count()

        retention_blocks = (
            self.retention_rule.raw_content_policy == "retain-restricted"
            or self.retention_rule.legal_hold
            or self.lifecycle_state in {
                RetentionLifeCycleState.HELD,
                RetentionLifeCycleState.AUDIT_LINKED,
            }
        )

        deletion_safe = (
            hold_count == 0
            and reference_count == 0
            and not retention_blocks
            and self.safety_status is None
        ) or (
            self.safety_status is not None
            and self.safety_status.deletion_safe
        )

        return SafetyStatus(
            deletion_safe=deletion_safe,
            reference_count=reference_count,
            hold_count=hold_count,
            audit_preserved=self.retention_rule.raw_content_policy
            in {"retain-restricted", "retain-governed"}
            or self.lifecycle_state == RetentionLifeCycleState.AUDIT_LINKED,
        )

    def generate_dry_run_report(
        self,
        *,
        dry_run_only: bool = True,
        rejection_reason: str | None = None,
    ) -> dict[str, Any]:
        """Generate a dry-run report for proposed action."""
        safety = self.evaluate_deletion_safety()

        action = self.proposed_action
        if safety.reference_count > 0 or safety.hold_count > 0:
            action = ProposedAction.NONE

        return {
            "object_id": self.object_id,
            "scope": self.scope,
            "size_bytes": self._estimate_size(),
            "retention_rule": self.retention_rule.model_dump(mode="json"),
            "hold_status": [
                {"hold_type": h.hold_type, "reason": h.reason} for h in self.holds
            ],
            "reference_proof": {
                "total_count": safety.reference_count,
                "canonical_count": len(self.references.canonical),
                "projected_count": len(self.references.projected),
            },
            "proposed_action": action.value,
            "dry_run_only": dry_run_only,
            "rejection_reason": rejection_reason or self._build_rejection_reason(safety),
            "safety_status": safety.model_dump(mode="json"),
        }

    def _estimate_size(self) -> int:
        """Estimate object size for reporting."""
        base_size = 1024
        return base_size + len(self.holds) * 512 + len(self.evidence_refs or []) * 256

    def _build_rejection_reason(self, safety: SafetyStatus) -> str | None:
        if safety.hold_count > 0:
            return f"object has {safety.hold_count} active holds blocking deletion"
        if safety.reference_count > 0:
            return f"object has {safety.reference_count} active references preventing cleanup"
        if not safety.audit_preserved:
            return "audit preservation required for this object type"
        return None


class RetentionPolicyService:
    """Service for evaluating retention policies and garbage collection eligibility."""

    def __init__(self, settings_path: str | None = None) -> None:
        self._settings_path = settings_path
        self._grace_period_hours = 24

    def evaluate_object(
        self,
        object_id: str,
        scope: str,
        lifecycle_state: RetentionLifeCycleState | None,
        retention_rule: RetentionRule,
        holds: list[RetentionHold] | None = None,
        references: ReferenceMap | None = None,
    ) -> RetentionStateMatrix:
        """Evaluate retention state for a given object."""
        holds_list = holds or []
        references_map = references or ReferenceMap()

        matrix = RetentionStateMatrix(
            object_id=object_id,
            scope=scope,
            lifecycle_state=lifecycle_state,
            retention_rule=retention_rule,
            holds=holds_list,
            references=references_map,
        )

        safety = matrix.evaluate_deletion_safety(
            grace_period_hours=self._grace_period_hours
        )
        matrix.safety_status = safety

        if safety.deletion_safe:
            matrix.proposed_action = ProposedAction.DELETE

        return matrix

    def validate_approval(
        self,
        approval: dict[str, Any],
        policy_version: str,
    ) -> bool:
        """Validate that approval meets requirements for destructive action."""
        if not approval.get("approved"):
            return False
        if not approval.get("approved_by"):
            return False
        if not approval.get("approval_hash"):
            return False
        if approval.get("policy_version") != policy_version:
            return False
        return True


def get_retention_policy_service() -> RetentionPolicyService:
    """Return singleton retention policy service instance."""
    return RetentionPolicyService()


__all__ = [
    "RetentionLifeCycleState",
    "HoldType",
    "ProposedAction",
    "RetentionRule",
    "RetentionHold",
    "ReferenceMap",
    "SafetyStatus",
    "RetentionStateMatrix",
    "RetentionPolicyService",
    "get_retention_policy_service",
]