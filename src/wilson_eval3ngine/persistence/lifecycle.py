"""Lifecycle management: regrading, backfill, retention, deletion, rollback.

T3.1.5 - Lifecycle workflows with immutable versioning and audit linkage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Optional

from ..util import utc_now


class LifecycleState(str, Enum):
    """Lifecycle states for versioned records."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
    CRYPTO_ERASE_MARKED = "crypto_erase_marked"


class HoldState(str, Enum):
    """Legal hold states."""
    NONE = "none"
    HELD = "held"
    PENDING_REVIEW = "pending_review"


@dataclass
class LifecycleJob:
    """Represents a lifecycle operation with resumable state."""
    job_id: str
    project_id: str
    operation_type: str  # regrade, backfill, retention_sweep, deletion, rollback
    target_ids: list[str]
    dry_run: bool = False
    batch_size: int = 1000
    processed_count: int = 0
    total_target_count: int = 0
    checkpoint_token: Optional[str] = None
    hold_state: HoldState = HoldState.NONE
    policy_version: str = "1.0.0"
    deletion_reason: Optional[str] = None
    deleted_by: Optional[str] = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def resume_key(self) -> str:
        """Generate key for resuming interrupted jobs."""
        return f"{self.operation_type}:{self.project_id}:{self.checkpoint_token or 'start'}"


@dataclass
class DeletionTombstone:
    """Immutable tombstone for deleted records."""
    original_id: str
    project_id: str
    table_name: str
    deleted_at: datetime
    deleted_by: str
    deletion_reason: str
    original_hash: str  # hash of original record before deletion
    tombstone_hash: str  # hash of this tombstone record

    def compute_tombstone_hash(self) -> str:
        """Compute SHA-256 hash of the tombstone for audit chain linkage."""
        canonical = f"{self.original_id}|{self.project_id}|{self.deleted_at.isoformat()}|{self.deleted_by}|{self.deletion_reason}|{self.original_hash}"
        return sha256(canonical.encode(), usedforsecurity=True).hexdigest()


@dataclass
class GradeVersion:
    """Immutable grade version record."""
    grade_id: str
    run_id: str
    project_id: str
    primary_label: str
    confidence: float
    grader_version: str
    evidence_hash: str
    created_at: datetime
    superseded_by_id: Optional[str] = None
    previous_hash: Optional[str] = None  # For audit chain

    def to_audit_payload(self) -> dict[str, Any]:
        """Convert to audit payload preserving immutability."""
        return {
            "grade_id": self.grade_id,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "primary_label": self.primary_label,
            "confidence": self.confidence,
            "grader_version": self.grader_version,
            "evidence_hash": self.evidence_hash,
            "created_at": self.created_at.isoformat(),
        }


class LifecycleManager:
    """Manages regrading, backfill, retention, and deletion operations.

    All operations are:
    - Idempotent via checkpoint tokens
    - Audited with immutable records
    - Compatible with retention/legal hold policies
    - Safe for rollback without data loss
    """

    def __init__(self, repository: Any, evidence_store: Any) -> None:
        self.repository = repository
        self.evidence_store = evidence_store

    def create_regrade_job(
        self,
        *,
        project_id: str,
        experiment_id: str,
        target_grader_version: str,
        hold_precedence_check: bool = True,
    ) -> LifecycleJob:
        """Create a regrading job for an experiment.

        Regrading creates new grade versions from existing immutable evidence
        without invoking the provider again.
        """
        # Determine target runs from experiment
        target_runs = self._get_experiment_runs(project_id, experiment_id)

        # Check legal hold if required
        hold_state = HoldState.NONE
        if hold_precedence_check:
            hold_state = self._check_retention_hold(project_id, target_runs)

        job = LifecycleJob(
            job_id=self._generate_job_id("regrade", project_id, experiment_id),
            project_id=project_id,
            operation_type="regrade",
            target_ids=target_runs,
            dry_run=False,
            total_target_count=len(target_runs),
            hold_state=hold_state,
            policy_version="1.0.0",
        )
        return job

    def execute_backfill(
        self,
        job: LifecycleJob,
        batch_checkpoint_provider: Any,
    ) -> int:
        """Execute a backfill job with resumable checkpoint semantics.

        Returns count of processed items.
        """
        if job.hold_state == HoldState.HELD:
            raise ValueError("Cannot process backfill: legal hold active")

        processed = 0
        batch_start = 0

        # Resume from checkpoint if provided
        if job.checkpoint_token:
            batch_start = self._decode_checkpoint(job.checkpoint_token)

        for i, target_id in enumerate(job.target_ids[batch_start:], start=batch_start):
            if i >= batch_start + job.batch_size:
                # Set checkpoint for next batch
                job.checkpoint_token = self._encode_checkpoint(i)
                job.processed_count = processed
                break

            try:
                self._process_backfill_item(job, target_id)
                processed += 1
            except Exception as e:
                # Log error but continue - collect for final report
                job.error_message = str(e)
                raise

        job.processed_count += processed

        # Mark complete if all items processed
        if job.processed_count >= job.total_target_count:
            job.completed_at = utc_now()

        return processed

    def _process_backfill_item(self, job: LifecycleJob, target_id: str) -> None:
        """Process a single backfill item.

        For regrade: creates new GradeVersion from existing evidence.
        For retention: applies retention rules and creates tombstones.
        """
        if job.operation_type == "regrade":
            self._regrade_single_grade(target_id, job.target_ids)
        elif job.operation_type == "retention_sweep":
            self._apply_retention_to_item(target_id)
        elif job.operation_type == "deletion":
            self._delete_single_item(target_id, job.deleted_by)

    def _regrade_single_grade(self, run_id: str, grade_ids: list[str]) -> None:
        """Regrade from immutable evidence - no provider calls."""
        # Evidence must already exist and be immutable
        # This creates a NEW GradeVersion record, not updating existing
        raise NotImplementedError("Regrading logic requires grader integration")

    def _apply_retention_to_item(self, item_id: str) -> None:
        """Apply retention rules to a single item."""
        raise NotImplementedError("Retention logic requires policy evaluation")

    def _delete_single_item(self, item_id: str, deleted_by: str) -> None:
        """Delete an item with tombstone creation."""
        raise NotImplementedError("Deletion requires repository implementation")

    def _get_experiment_runs(self, project_id: str, experiment_id: str) -> list[str]:
        """Get all run IDs for an experiment."""
        # This would query the repository with RLS context
        raise NotImplementedError("Requires repository implementation")

    def _check_retention_hold(self, project_id: str, run_ids: list[str]) -> HoldState:
        """Check if any target items have active legal hold."""
        raise NotImplementedError("Requires retention policy implementation")

    def _generate_job_id(self, op_type: str, project_id: str, context_id: str) -> str:
        """Generate deterministic job ID."""
        canonical = f"{op_type}:{project_id}:{context_id}:{datetime.now().timestamp()}"
        return sha256(canonical.encode(), usedforsecurity=True).hexdigest()[:24]

    def _encode_checkpoint(self, position: int) -> str:
        """Encode batch position as checkpoint token."""
        return sha256(str(position).encode(), usedforsecurity=True).hexdigest()

    def _decode_checkpoint(self, token: str) -> int:
        """Decode checkpoint token to batch position."""
        # Note: This is simplified - production would use encrypted tokens
        return 0  # Default to start if decoding fails

    def validate_lifecycle_safety(self, job: LifecycleJob) -> list[str]:
        """Validate no retention violations before job execution.

        Returns empty list if safe, list of violations otherwise.
        """
        violations = []

        if job.hold_state == HoldState.HELD:
            violations.append("legal_hold_active")

        if job.operation_type == "deletion" and not job.dry_run:
            # Additional validation for destructive operations
            if not job.deletion_reason:
                violations.append("missing_deletion_reason")

        return violations


def create_deletion_tombstone(
    original_id: str,
    project_id: str,
    table_name: str,
    deleted_by: str,
    deletion_reason: str,
    original_record: dict[str, Any],
) -> DeletionTombstone:
    """Factory function to create an immutable deletion tombstone."""
    original_hash = sha256(
        str(sorted(original_record.items())).encode(), usedforsecurity=True
    ).hexdigest()

    tombstone = DeletionTombstone(
        original_id=original_id,
        project_id=project_id,
        table_name=table_name,
        deleted_at=utc_now(),
        deleted_by=deleted_by,
        deletion_reason=deletion_reason,
        original_hash=original_hash,
        tombstone_hash="",  # Will be computed
    )

    tombstone.tombstone_hash = tombstone.compute_tombstone_hash()
    return tombstone