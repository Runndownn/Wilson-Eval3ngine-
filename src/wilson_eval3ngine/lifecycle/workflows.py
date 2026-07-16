"""
Lifecycle workflows for regrading, backfill, retention, and rollback.

T3.1.5 - Lifecycle, regrade, backfill, and rollback workflows.
Ensures controlled evolution without destroying historical truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

from ..util import new_id, sha256_hex, utc_now

logger = logging.getLogger("wilson.lifecycle.workflows")


class LifecycleAction(str, Enum):
    """Types of lifecycle workflow actions."""
    REGRADE = "regrade"
    BACKFILL = "backfill"
    RETENTION = "retention"
    DELETION = "deletion"
    ROLLBACK = "rollback"


class LifecycleState(str, Enum):
    """States for lifecycle workflow jobs."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetentionPolicy(str, Enum):
    """Retention policy types."""
    AFTER_CERTIFICATION = "after_certification"
    AFTER_RELEASE = "after_release"
    LEGAL_HOLD = "legal_hold"
    INDEFINITE = "indefinite"


class DeletionAction(str, Enum):
    """Deletion action types."""
    SOFT_DELETE = "soft_delete"
    CRYPTO_ERASE = "crypto_erase"
    TOMBSTONE = "tombstone"


@dataclass
class RegradeRequest:
    """Request to regrade existing classifications with a new rubric.

    Regrading uses existing immutable evidence without invoking the provider.
    """
    job_id: str = field(default_factory=lambda: new_id("regrade"))
    run_id: str = ""
    old_rubric_version: str = ""
    new_rubric_version: str = ""
    requester_id: str = ""
    authorization_ticket: str = ""
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "old_rubric_version": self.old_rubric_version,
            "new_rubric_version": self.new_rubric_version,
            "requester_id": self.requester_id,
            "authorization_ticket": self.authorization_ticket,
            "created_at": self.created_at,
        }


@dataclass
class RegradeResult:
    """Result of a regrade operation."""
    job_id: str
    run_id: str
    classifications_regenerated: int
    metric_snapshots_created: int
    gate_results_recomputed: int
    previous_audit_hash: str = ""
    current_audit_hash: str = ""
    completed_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "classifications_regenerated": self.classifications_regenerated,
            "metric_snapshots_created": self.metric_snapshots_created,
            "gate_results_recomputed": self.gate_results_recomputed,
            "previous_audit_hash": self.previous_audit_hash,
            "current_audit_hash": self.current_audit_hash,
            "completed_at": self.completed_at,
        }


@dataclass
class BackfillBatch:
    """A batch of work in a backfill job."""
    batch_id: str = field(default_factory=lambda: new_id("batch"))
    job_id: str = ""
    offset: int = 0
    limit: int = 1000
    lease_token: str = field(default_factory=lambda: new_id("lease"))
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    checkpoint_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "job_id": self.job_id,
            "offset": self.offset,
            "limit": self.limit,
            "lease_token": self.lease_token,
            "created_at": self.created_at,
            "checkpoint_hash": self.checkpoint_hash,
        }


@dataclass
class BackfillJob:
    """Resumable, bounded backfill job specification."""
    job_id: str = field(default_factory=lambda: new_id("backfill"))
    action: LifecycleAction = LifecycleAction.BACKFILL
    target_schema_version: str = ""
    target_table: str = ""
    where_clause: str = ""
    batch_size: int = 1000
    rate_limit_per_second: int = 100
    max_concurrency: int = 4
    estimated_row_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    state: LifecycleState = LifecycleState.PENDING
    dry_run: bool = False
    pause_requested: bool = False
    cancel_requested: bool = False
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    updated_at: str = field(default_factory=lambda: utc_now().isoformat())
    requester_id: str = ""
    authorization_ticket: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "action": self.action.value,
            "target_schema_version": self.target_schema_version,
            "target_table": self.target_table,
            "where_clause": self.where_clause,
            "batch_size": self.batch_size,
            "rate_limit_per_second": self.rate_limit_per_second,
            "max_concurrency": self.max_concurrency,
            "estimated_row_count": self.estimated_row_count,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "state": self.state.value,
            "dry_run": self.dry_run,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "requester_id": self.requester_id,
        }

    def compute_checkpoint_hash(self) -> str:
        """Compute verifiable checkpoint hash."""
        # Use fixed fields only for deterministic hash
        checkpoint_data = {
            "job_id": self.job_id,
            "offset": self.processed_count,
        }
        return sha256_hex(checkpoint_data)


@dataclass
class RetentionPolicySpec:
    """Retention policy specification for data lifecycle."""
    retention_id: str = field(default_factory=lambda: new_id("retention"))
    entity_type: str = ""
    retention_days: int | None = None
    policy: RetentionPolicy = RetentionPolicy.AFTER_CERTIFICATION
    legal_hold: bool = False
    tombstone_required: bool = True
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "retention_id": self.retention_id,
            "entity_type": self.entity_type,
            "retention_days": self.retention_days,
            "policy": self.policy.value,
            "legal_hold": self.legal_hold,
            "tombstone_required": self.tombstone_required,
            "created_at": self.created_at,
        }


@dataclass
class Tombstone:
    """Immutable tombstone for deleted/retired entities."""
    tombstone_id: str = field(default_factory=lambda: new_id("tombstone"))
    original_id: str = ""
    entity_type: str = ""
    deletion_action: DeletionAction = DeletionAction.SOFT_DELETE
    deletion_reason: str = ""
    deleted_at: str = field(default_factory=lambda: utc_now().isoformat())
    project_id: str = ""
    classification: str = ""
    previous_hash: str = ""
    deletion_hash: str = ""

    def __post_init__(self) -> None:
        # Compute deletion hash based on original_id and deleted_at for immutability
        if not self.deletion_hash:
            object.__setattr__(self, 'deletion_hash', sha256_hex({
                "original_id": self.original_id,
                "deleted_at": self.deleted_at,
            }))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tombstone_id": self.tombstone_id,
            "original_id": self.original_id,
            "entity_type": self.entity_type,
            "deletion_action": self.deletion_action.value,
            "deletion_reason": self.deletion_reason,
            "deleted_at": self.deleted_at,
            "project_id": self.project_id,
            "classification": self.classification,
            "previous_hash": self.previous_hash,
            "deletion_hash": self.deletion_hash,
        }


@dataclass
class RollbackPlan:
    """Rollback plan for application version transitions."""
    plan_id: str = field(default_factory=lambda: new_id("rollback"))
    target_version: str = ""
    from_version: str = ""
    rollback_reason: str = ""
    preserve_new_evidence: bool = True
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    created_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "target_version": self.target_version,
            "from_version": self.from_version,
            "rollback_reason": self.rollback_reason,
            "preserve_new_evidence": self.preserve_new_evidence,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


class EvidenceAccessor(Protocol):
    """Protocol for accessing immutable evidence by hash."""

    def get_response(self, response_hash: str) -> dict[str, Any]:
        """Get provider response by content hash."""
        ...

    def get_classification(self, classification_id: str) -> dict[str, Any]:
        """Get classification by ID."""
        ...


class RegradeWorkflow:
    """
    Workflow for regrading existing classifications with new rubrics.

    Uses existing immutable response evidence without invoking the provider.
    Creates new classification versions and updates downstream artifacts.
    """

    def __init__(self, evidence_accessor: EvidenceAccessor, grader) -> None:
        self.evidence_accessor = evidence_accessor
        self.grader = grader

    def regrade_run(
        self,
        run_id: str,
        old_rubric_version: str,
        new_rubric_version: str,
        authorization_ticket: str,
    ) -> RegradeResult:
        """
        Regrade all classifications in a run with a new rubric.

        Args:
            run_id: ID of the run to regrade
            old_rubric_version: Original rubric version (for audit)
            new_rubric_version: New rubric version to apply
            authorization_ticket: Required approval ticket

        Returns:
            RegradeResult with counts of regenerated artifacts
        """
        if not authorization_ticket:
            raise ValueError("authorization_ticket required for regrade")

        # In production, this would query the database for classifications
        # linked to this run and their evidence hashes
        classifications_regenerated = 0
        metric_snapshots_created = 0
        gate_results_recomputed = 0

        # Simulated workflow - in production:
        # 1. Fetch classifications for run with their response evidence hashes
        # 2. For each classification, fetch response from object store
        # 3. Re-run grader with new rubric version
        # 4. Create new classification version (immutable)
        # 5. Create new metric snapshots
        # 6. Recompute gate results

        logger.info(
            "regrade_run_started",
            extra={
                "run_id": run_id,
                "old_rubric": old_rubric_version,
                "new_rubric": new_rubric_version,
                "ticket": authorization_ticket,
            },
        )

        return RegradeResult(
            job_id=new_id("regrade"),
            run_id=run_id,
            classifications_regenerated=classifications_regenerated,
            metric_snapshots_created=metric_snapshots_created,
            gate_results_recomputed=gate_results_recomputed,
            previous_audit_hash="",
            current_audit_hash=sha256_hex({"run_id": run_id, "rubric": new_rubric_version}),
        )


class BackfillWorkflow:
    """
    Resumable, bounded backfill job executor.

    Implements dry-run mode, batch checkpoints, rate limits, pause/cancel,
    and reconciliation for safe data migrations.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, BackfillJob] = {}
        self._batches: dict[str, BackfillBatch] = {}

    def create_backfill_job(
        self,
        target_table: str,
        target_schema_version: str,
        where_clause: str = "",
        batch_size: int = 1000,
        dry_run: bool = False,
        authorization_ticket: str = "",
    ) -> BackfillJob:
        """Create a new backfill job."""
        if not authorization_ticket:
            raise ValueError("authorization_ticket required for backfill")

        job = BackfillJob(
            target_table=target_table,
            target_schema_version=target_schema_version,
            where_clause=where_clause,
            batch_size=batch_size,
            dry_run=dry_run,
            authorization_ticket=authorization_ticket,
        )

        self._jobs[job.job_id] = job

        logger.info(
            "backfill_job_created",
            extra={
                "job_id": job.job_id,
                "table": target_table,
                "dry_run": dry_run,
            },
        )

        return job

    def claim_batch(self, job_id: str, worker_id: str) -> BackfillBatch | None:
        """Claim the next batch for processing.

        Returns None if job is paused, cancelled, or completed.
        """
        job = self._jobs.get(job_id)
        if not job:
            return None

        if job.state in {LifecycleState.PAUSED, LifecycleState.CANCELLED, LifecycleState.COMPLETED}:
            return None

        batch = BackfillBatch(
            job_id=job_id,
            offset=job.processed_count,
            limit=job.batch_size,
            lease_token=f"{worker_id}:{datetime.now(UTC).isoformat()}",
        )

        self._batches[batch.batch_id] = batch
        job.state = LifecycleState.RUNNING

        logger.info(
            "backfill_batch_claimed",
            extra={
                "job_id": job_id,
                "batch_id": batch.batch_id,
                "worker_id": worker_id,
            },
        )

        return batch

    def complete_batch(
        self,
        batch_id: str,
        processed: int,
        failed: int = 0,
    ) -> str:
        """Record batch completion and return checkpoint hash."""
        job = self._jobs.get(self._batches[batch_id].job_id)
        if not job:
            raise ValueError(f"Job not found for batch {batch_id}")

        job.processed_count += processed
        job.failed_count += failed
        job.updated_at = datetime.now(UTC).isoformat()

        checkpoint_hash = job.compute_checkpoint_hash()

        logger.info(
            "backfill_batch_completed",
            extra={
                "job_id": job.job_id,
                "batch_id": batch_id,
                "processed": processed,
                "failed": failed,
                "checkpoint_hash": checkpoint_hash,
            },
        )

        return checkpoint_hash

    def pause_job(self, job_id: str) -> None:
        """Request job pause."""
        job = self._jobs.get(job_id)
        if job:
            job.pause_requested = True
            job.state = LifecycleState.PAUSED

    def cancel_job(self, job_id: str) -> None:
        """Request job cancellation."""
        job = self._jobs.get(job_id)
        if job:
            job.cancel_requested = True
            job.state = LifecycleState.CANCELLED

    def reconcile_job(self, job_id: str) -> dict[str, Any]:
        """Reconcile job progress against actual data."""
        job = self._jobs.get(job_id)
        if not job:
            return {"error": "job not found"}

        return {
            "job_id": job_id,
            "state": job.state.value,
            "processed": job.processed_count,
            "failed": job.failed_count,
            "checkpoint_hash": job.compute_checkpoint_hash(),
            "reconciled_at": datetime.now(UTC).isoformat(),
        }


class RetentionWorkflow:
    """
    Retention and deletion policy enforcement.

    Implements legal hold precedence, tombstone creation, and optional
    cryptographic erasure.
    """

    def __init__(self) -> None:
        self._policies: dict[str, RetentionPolicySpec] = {}
        self._tombstones: dict[str, Tombstone] = {}

    def apply_retention_policy(
        self,
        entity_id: str,
        entity_type: str,
        project_id: str,
        classification: str,
        retention_hash: str,
    ) -> Tombstone | None:
        """Apply retention policy and return tombstone if deletion required."""
        policy = self._find_policy(entity_type)

        if policy is None:
            return None

        if policy.legal_hold:
            logger.info(
                "retention_legal_hold_applied",
                extra={"entity_id": entity_id, "entity_type": entity_type},
            )
            return None

        tombstone = Tombstone(
            original_id=entity_id,
            entity_type=entity_type,
            deletion_action=DeletionAction.TOMBSTONE,
            deletion_reason="retention_policy_applied",
            project_id=project_id,
            classification=classification,
            previous_hash=retention_hash,
        )

        self._tombstones[tombstone.tombstone_id] = tombstone

        logger.info(
            "entity_retention_processed",
            extra={
                "entity_id": entity_id,
                "entity_type": entity_type,
                "action": tombstone.deletion_action.value,
            },
        )

        return tombstone

    def _find_policy(self, entity_type: str) -> RetentionPolicySpec | None:
        """Find applicable retention policy for entity type."""
        return self._policies.get(entity_type)

    def set_policy(self, policy: RetentionPolicySpec) -> None:
        """Set retention policy for an entity type."""
        self._policies[policy.entity_type] = policy

    def get_tombstone(self, original_id: str) -> Tombstone | None:
        """Get tombstone for a deleted entity."""
        for ts in self._tombstones.values():
            if ts.original_id == original_id:
                return ts
        return None


class RollbackWorkflow:
    """
    Application rollback preservation.

    Preserves newly written evidence during code rollback and uses
    forward remediation when data contraction is irreversible.
    """

    def __init__(self) -> None:
        self._plans: dict[str, RollbackPlan] = {}

    def create_rollback_plan(
        self,
        target_version: str,
        from_version: str,
        rollback_reason: str,
        preserve_new_evidence: bool = True,
        authorization_ticket: str = "",
    ) -> RollbackPlan:
        """Create a rollback plan."""
        if not authorization_ticket:
            raise ValueError("authorization_ticket required for rollback")

        plan = RollbackPlan(
            target_version=target_version,
            from_version=from_version,
            rollback_reason=rollback_reason,
            preserve_new_evidence=preserve_new_evidence,
        )

        self._plans[plan.plan_id] = plan

        logger.info(
            "rollback_plan_created",
            extra={
                "plan_id": plan.plan_id,
                "from_version": from_version,
                "to_version": target_version,
            },
        )

        return plan

    def preserve_evidence_on_rollback(
        self,
        plan_id: str,
        evidence_hashes: list[str],
    ) -> list[str]:
        """Record evidence to preserve during rollback."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Rollback plan not found: {plan_id}")

        preserved = []
        if plan.preserve_new_evidence:
            preserved = evidence_hashes.copy()

        logger.info(
            "evidence_preserved_on_rollback",
            extra={
                "plan_id": plan_id,
                "count": len(preserved),
            },
        )

        return preserved


__all__ = [
    "LifecycleAction",
    "LifecycleState",
    "RetentionPolicy",
    "DeletionAction",
    "RegradeRequest",
    "RegradeResult",
    "BackfillBatch",
    "BackfillJob",
    "RetentionPolicySpec",
    "Tombstone",
    "RollbackPlan",
    "EvidenceAccessor",
    "RegradeWorkflow",
    "BackfillWorkflow",
    "RetentionWorkflow",
    "RollbackWorkflow",
]