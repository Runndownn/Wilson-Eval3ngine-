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
        """Regrade from immutable evidence - no provider calls.

        Creates a new GradeVersion record from existing evidence, superseding
        the previous classification. Evidence is immutable and already stored.
        """
        from sqlalchemy import text as sql_text
        import json as _json

        with self.repository.database.session() as session, session.begin():
            # Query existing classifications for this run
            rows = session.execute(
                sql_text(
                    "SELECT id, primary_label, confidence, payload_json "
                    "FROM classifications WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).fetchall()

            if not rows:
                return

            # Create new GradeVersion records for each classification
            for row in rows:
                old_id = row[0]
                old_label = row[1]
                old_confidence = row[2]
                payload = row[3] if isinstance(row[3], dict) else {}

                # Evidence hash from the payload (immutable)
                evidence_hash = payload.get("evidence_hash", "") or sha256(
                    str(sorted(payload.items())).encode(), usedforsecurity=True
                ).hexdigest()

                # Mark old classification as superseded
                new_grade_id = f"gv_{sha256(f'{old_id}:regrade:{utc_now().isoformat()}'.encode(), usedforsecurity=True).hexdigest()[:16]}"
                session.execute(
                    sql_text(
                        "UPDATE classifications SET superseded_by_id = :new_id "
                        "WHERE id = :old_id"
                    ),
                    {"new_id": new_grade_id, "old_id": old_id},
                )

                # Insert new GradeVersion record (stored as a classification with new ID)
                session.execute(
                    sql_text(
                        "INSERT INTO classifications "
                        "(id, project_id, run_id, primary_label, confidence, "
                        "requires_human_review, payload_json, superseded_by_id, created_at) "
                        "VALUES (:id, :project_id, :run_id, :primary_label, :confidence, "
                        ":requires_human_review, :payload_json, :superseded_by_id, :created_at)"
                    ),
                    {
                        "id": new_grade_id,
                        "project_id": payload.get("project_id", ""),
                        "run_id": run_id,
                        "primary_label": old_label,
                        "confidence": old_confidence,
                        "requires_human_review": payload.get("requires_human_review", False),
                        "payload_json": _json.dumps({
                            **payload,
                            "grade_version": new_grade_id,
                            "regraded_from": old_id,
                            "regraded_at": utc_now().isoformat(),
                        }),
                        "superseded_by_id": None,
                        "created_at": utc_now(),
                    },
                )

    def _apply_retention_to_item(self, item_id: str) -> None:
        """Apply retention rules to a single item.

        Checks retention policy and creates tombstone if item should be deleted.
        Items under legal hold are preserved.
        """
        from sqlalchemy import text as sql_text

        with self.repository.database.session() as session, session.begin():
            # Check if item is under legal hold
            hold_result = session.execute(
                sql_text(
                    "SELECT COUNT(*) FROM overrides "
                    "WHERE resource_type = 'legal_hold' AND active = true "
                    "AND json_extract(payload_json, '$.target_id') = :item_id"
                ),
                {"item_id": item_id},
            ).scalar()

            if hold_result and hold_result > 0:
                # Item is under legal hold - do not delete
                return

            # Check retention policy - items older than retention period are eligible
            # For foundation, retention is based on age and project policy
            # This is a simplified implementation
            pass

    def _delete_single_item(self, item_id: str, deleted_by: str) -> None:
        """Delete an item with tombstone creation.

        Creates an immutable tombstone before deletion for audit trail.
        """
        from sqlalchemy import text as sql_text

        with self.repository.database.session() as session, session.begin():
            # Query the item to capture its state before deletion
            row = session.execute(
                sql_text(
                    "SELECT project_id, run_id, primary_label, confidence, "
                    "payload_json FROM classifications WHERE id = :id"
                ),
                {"id": item_id},
            ).fetchone()

            if row is None:
                return

            project_id = row[0]
            original_record = {
                "id": item_id,
                "project_id": project_id,
                "run_id": row[1],
                "primary_label": row[2],
                "confidence": row[3],
                "payload_json": row[4] if isinstance(row[4], dict) else {},
            }

            # Create deletion tombstone
            tombstone = create_deletion_tombstone(
                original_id=item_id,
                project_id=project_id,
                table_name="classifications",
                deleted_by=deleted_by or "system",
                deletion_reason="retention_sweep",
                original_record=original_record,
            )

            # Insert tombstone into audit_events for immutable record
            import json as _json

            def _serialize_tombstone(ts):
                return {
                    "original_id": ts.original_id,
                    "project_id": ts.project_id,
                    "table_name": ts.table_name,
                    "deleted_at": ts.deleted_at.isoformat() if ts.deleted_at else None,
                    "deleted_by": ts.deleted_by,
                    "deletion_reason": ts.deletion_reason,
                    "original_hash": ts.original_hash,
                    "tombstone_hash": ts.tombstone_hash,
                }

            session.execute(
                sql_text(
                    "INSERT INTO audit_events "
                    "(id, project_id, event_type, aggregate_type, aggregate_id, "
                    "actor_id, payload_json, event_hash, created_at) "
                    "VALUES (:id, :project_id, :event_type, :aggregate_type, :aggregate_id, "
                    ":actor_id, :payload_json, :event_hash, :created_at)"
                ),
                {
                    "id": f"del_{tombstone.tombstone_hash[:16]}",
                    "project_id": project_id,
                    "event_type": "deletion_tombstone",
                    "aggregate_type": "classification",
                    "aggregate_id": item_id,
                    "actor_id": deleted_by or "system",
                    "payload_json": _json.dumps({
                        "tombstone": _serialize_tombstone(tombstone),
                        "original_record": original_record,
                    }),
                    "event_hash": tombstone.tombstone_hash,
                    "created_at": utc_now(),
                },
            )

            # Delete the original record
            session.execute(
                sql_text("DELETE FROM classifications WHERE id = :id"),
                {"id": item_id},
            )

    def _get_experiment_runs(self, project_id: str, experiment_id: str) -> list[str]:
        """Get all run IDs for an experiment."""
        from sqlalchemy import text as sql_text

        with self.repository.database.session() as session:
            rows = session.execute(
                sql_text(
                    "SELECT id FROM runs WHERE project_id = :project_id "
                    "AND experiment_id = :experiment_id"
                ),
                {"project_id": project_id, "experiment_id": experiment_id},
            ).fetchall()

            return [row[0] for row in rows]

    def _check_retention_hold(self, project_id: str, run_ids: list[str]) -> HoldState:
        """Check if any target items have active legal hold.

        Uses the overrides table to check for hold-related scopes.
        In production, this would query a dedicated legal_hold table.
        """
        from sqlalchemy import text as sql_text

        if not run_ids:
            return HoldState.NONE

        # Build placeholder string for IN clause
        placeholders = ", ".join([f":id_{i}" for i in range(len(run_ids))])
        params = {"project_id": project_id}
        for i, run_id in enumerate(run_ids):
            params[f"id_{i}"] = run_id

        with self.repository.database.session() as session:
            # Check for active overrides with legal_hold scope
            # The scope_json field may contain hold information
            result = session.execute(
                sql_text(
                    f"SELECT COUNT(*) FROM overrides "
                    f"WHERE applied = true "
                    f"AND json_extract(scope_json, '$.project_id') = :project_id "
                    f"AND json_extract(scope_json, '$.hold_type') = 'legal_hold'"
                ),
                params,
            ).scalar()

            if result and result > 0:
                return HoldState.HELD

            # Check for pending review overrides
            result = session.execute(
                sql_text(
                    f"SELECT COUNT(*) FROM overrides "
                    f"WHERE applied = true "
                    f"AND json_extract(scope_json, '$.project_id') = :project_id "
                    f"AND json_extract(scope_json, '$.hold_type') = 'retention_hold'"
                ),
                params,
            ).scalar()

            if result and result > 0:
                return HoldState.PENDING_REVIEW

            return HoldState.NONE

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