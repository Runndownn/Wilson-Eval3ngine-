"""Unit tests for lifecycle management (T3.1.5 - TODO 19)."""
from __future__ import annotations

from datetime import datetime, timezone


from wilson_eval3ngine.persistence.lifecycle import (
    DeletionTombstone,
    GradeVersion,
    HoldState,
    LifecycleJob,
    LifecycleManager,
    LifecycleState,
    create_deletion_tombstone,
)


class TestLifecycleState:
    """Test lifecycle state enum values."""

    def test_active_state_exists(self) -> None:
        assert LifecycleState.ACTIVE.value == "active"

    def test_superseded_state_exists(self) -> None:
        assert LifecycleState.SUPERSEDED.value == "superseded"

    def test_deleted_state_exists(self) -> None:
        assert LifecycleState.DELETED.value == "deleted"

    def test_crypto_erase_marked_state_exists(self) -> None:
        assert LifecycleState.CRYPTO_ERASE_MARKED.value == "crypto_erase_marked"


class TestHoldState:
    """Test hold state enum values."""

    def test_none_state_exists(self) -> None:
        assert HoldState.NONE.value == "none"

    def test_held_state_exists(self) -> None:
        assert HoldState.HELD.value == "held"

    def test_pending_review_state_exists(self) -> None:
        assert HoldState.PENDING_REVIEW.value == "pending_review"


class TestDeletionTombstone:
    """Test immutable deletion tombstone creation."""

    def test_tombstone_has_required_fields(self) -> None:
        tombstone = DeletionTombstone(
            original_id="run_123",
            project_id="proj_456",
            table_name="classifications",
            deleted_at=datetime.now(timezone.utc),
            deleted_by="operator@example.com",
            deletion_reason="retention_expired",
            original_hash="abc123",
            tombstone_hash="def456",
        )
        assert tombstone.original_id == "run_123"
        assert tombstone.project_id == "proj_456"
        assert tombstone.table_name == "classifications"

    def test_tombstone_hash_is_deterministic(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        tombstone = DeletionTombstone(
            original_id="run_123",
            project_id="proj_456",
            table_name="classifications",
            deleted_at=now,
            deleted_by="operator@example.com",
            deletion_reason="retention_expired",
            original_hash="abc123",
            tombstone_hash="",
        )
        h1 = tombstone.compute_tombstone_hash()
        h2 = tombstone.compute_tombstone_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length


class TestGradeVersion:
    """Test immutable grade version records."""

    def test_grade_version_has_audit_payload(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        version = GradeVersion(
            grade_id="grade_001",
            run_id="run_001",
            project_id="proj_001",
            primary_label="safe_compliance",
            confidence=0.95,
            grader_version="fusion-foundation-1.0.0",
            evidence_hash="evidence_sha256",
            created_at=now,
        )
        payload = version.to_audit_payload()
        assert payload["grade_id"] == "grade_001"
        assert payload["primary_label"] == "safe_compliance"
        assert "created_at" in payload

    def test_grade_version_superseded_by_optional(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        version = GradeVersion(
            grade_id="grade_001",
            run_id="run_001",
            project_id="proj_001",
            primary_label="safe_compliance",
            confidence=0.95,
            grader_version="fusion-foundation-1.0.0",
            evidence_hash="evidence_sha256",
            created_at=now,
            superseded_by_id="grade_002",
        )
        assert version.superseded_by_id == "grade_002"


class TestLifecycleJob:
    """Test lifecycle job creation and resume semantics."""

    def test_job_has_checkpoint_key(self) -> None:
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="regrade",
            target_ids=["run_001", "run_002", "run_003"],
        )
        key = job.resume_key()
        assert "regrade" in key
        assert "proj_001" in key

    def test_job_dry_run_default_false(self) -> None:
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="regrade",
            target_ids=["run_001"],
        )
        assert job.dry_run is False

    def test_job_hold_state_default_none(self) -> None:
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="regrade",
            target_ids=["run_001"],
        )
        assert job.hold_state == HoldState.NONE

    def test_job_batch_size_default_sensible(self) -> None:
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="regrade",
            target_ids=["run_001"],
        )
        assert job.batch_size >= 100  # Sensible default for batch processing


class TestLifecycleManager:
    """Test lifecycle manager validation and safety."""

    def test_validate_lifecycle_safety_returns_violations(self) -> None:
        manager = LifecycleManager(repository=None, evidence_store=None)  # type: ignore
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="regrade",
            target_ids=["run_001"],
            hold_state=HoldState.HELD,
        )
        violations = manager.validate_lifecycle_safety(job)
        assert "legal_hold_active" in violations

    def test_validate_deletion_requires_reason(self) -> None:
        manager = LifecycleManager(repository=None, evidence_store=None)  # type: ignore
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="deletion",
            target_ids=["run_001"],
            deletion_reason="",  # Empty reason
        )
        violations = manager.validate_lifecycle_safety(job)
        assert "missing_deletion_reason" in violations

    def test_dry_run_no_violations(self) -> None:
        manager = LifecycleManager(repository=None, evidence_store=None)  # type: ignore
        job = LifecycleJob(
            job_id="job_001",
            project_id="proj_001",
            operation_type="deletion",
            target_ids=["run_001"],
            deletion_reason="test",
            dry_run=True,
        )
        violations = manager.validate_lifecycle_safety(job)
        assert len(violations) == 0


class TestCreateDeletionTombstone:
    """Test tombstone factory function."""

    def test_factory_creates_tombstone(self) -> None:
        original = {"field": "value", "number": 42}
        tombstone = create_deletion_tombstone(
            original_id="run_001",
            project_id="proj_001",
            table_name="runs",
            deleted_by="operator@example.com",
            deletion_reason="retention_expired",
            original_record=original,
        )
        assert tombstone.original_id == "run_001"
        assert tombstone.table_name == "runs"
        assert len(tombstone.original_hash) == 64
        assert len(tombstone.tombstone_hash) == 64

    def test_tombstone_hash_derived_from_data(self) -> None:
        original = {"field": "value"}
        tombstone1 = create_deletion_tombstone(
            original_id="run_001",
            project_id="proj_001",
            table_name="runs",
            deleted_by="operator@example.com",
            deletion_reason="retention_expired",
            original_record=original,
        )
        tombstone2 = create_deletion_tombstone(
            original_id="run_002",  # Different original
            project_id="proj_001",
            table_name="runs",
            deleted_by="operator@example.com",
            deletion_reason="retention_expired",
            original_record=original,
        )
        # Different original_id should produce different hash
        assert tombstone1.tombstone_hash != tombstone2.tombstone_hash