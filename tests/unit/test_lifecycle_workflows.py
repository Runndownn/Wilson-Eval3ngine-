"""Tests for lifecycle workflows.

Validates T3.1.5 requirements for regrade, backfill, retention, and rollback.
"""

from __future__ import annotations

import pytest

from wilson_eval3ngine.lifecycle.workflows import (
    BackfillBatch,
    BackfillJob,
    BackfillWorkflow,
    DeletionAction,
    LifecycleAction,
    LifecycleState,
    RegradeRequest,
    RegradeWorkflow,
    RetentionPolicy,
    RetentionPolicySpec,
    RetentionWorkflow,
    RollbackPlan,
    RollbackWorkflow,
    Tombstone,
)


class TestRegradeRequest:
    """Tests for regrade request structure."""

    def test_regrade_request_defaults(self):
        """Regrade request has generated defaults."""
        req = RegradeRequest(
            run_id="run_001",
            old_rubric_version="v1.0.0",
            new_rubric_version="v1.1.0",
            requester_id="user_001",
        )
        assert req.job_id != ""
        assert req.run_id == "run_001"
        assert req.created_at != ""

    def test_regrade_request_serialization(self):
        """Regrade request serializes correctly."""
        req = RegradeRequest(
            run_id="run_002",
            old_rubric_version="v1.0.0",
            new_rubric_version="v1.1.0",
        )
        d = req.to_dict()
        assert d["run_id"] == "run_002"
        assert d["old_rubric_version"] == "v1.0.0"
        assert d["new_rubric_version"] == "v1.1.0"


class TestRegradeWorkflow:
    """Tests for regrade workflow execution."""

    def test_regrade_requires_authorization(self):
        """Regrade fails without authorization ticket."""
        workflow = RegradeWorkflow(evidence_accessor=None, grader=None)

        with pytest.raises(ValueError, match="authorization_ticket"):
            workflow.regrade_run(
                run_id="run_001",
                old_rubric_version="v1.0.0",
                new_rubric_version="v1.1.0",
                authorization_ticket="",
            )

    def test_regrade_creates_result(self):
        """Regrade returns proper result structure."""
        workflow = RegradeWorkflow(evidence_accessor=None, grader=None)

        result = workflow.regrade_run(
            run_id="run_001",
            old_rubric_version="v1.0.0",
            new_rubric_version="v1.1.0",
            authorization_ticket="ticket_abc",
        )

        assert result.job_id != ""
        assert result.run_id == "run_001"
        assert result.classifications_regenerated == 0
        assert result.current_audit_hash != ""


class TestBackfillJob:
    """Tests for backfill job structure."""

    def test_backfill_job_defaults(self):
        """Backfill job has sensible defaults."""
        job = BackfillJob(
            target_table="responses",
            target_schema_version="we3.response.v2",
        )
        assert job.batch_size == 1000
        assert job.rate_limit_per_second == 100
        assert job.max_concurrency == 4
        assert job.state == LifecycleState.PENDING
        assert job.dry_run is False

    def test_backfill_job_checkpoint_hash(self):
        """Checkpoint hash is computed deterministically from offset."""
        job = BackfillJob(
            job_id="backfill_test_001",
            target_table="responses",
            target_schema_version="we3.response.v2",
            processed_count=1000,
        )
        hash1 = job.compute_checkpoint_hash()

        job2 = BackfillJob(
            job_id="backfill_test_001",
            target_table="responses",
            target_schema_version="we3.response.v2",
            processed_count=1000,
        )
        hash2 = job2.compute_checkpoint_hash()

        assert hash1 == hash2

    def test_backfill_job_checkpoint_hash_changes_with_offset(self):
        """Checkpoint hash changes when offset changes."""
        job = BackfillJob(
            job_id="backfill_test_002",
            target_table="responses",
            target_schema_version="we3.response.v2",
            processed_count=1000,
        )
        hash_at_1000 = job.compute_checkpoint_hash()

        job.processed_count = 2000
        hash_at_2000 = job.compute_checkpoint_hash()

        assert hash_at_1000 != hash_at_2000

    def test_backfill_job_serialization(self):
        """Backfill job serializes correctly."""
        job = BackfillJob(
            target_table="responses",
            target_schema_version="we3.response.v2",
            batch_size=5000,
            dry_run=True,
        )
        d = job.to_dict()
        assert d["target_table"] == "responses"
        assert d["dry_run"] is True


class TestBackfillWorkflow:
    """Tests for backfill workflow execution."""

    def test_create_job_requires_authorization(self):
        """Create job fails without authorization."""
        wf = BackfillWorkflow()

        with pytest.raises(ValueError, match="authorization_ticket"):
            wf.create_backfill_job(
                target_table="responses",
                target_schema_version="we3.response.v2",
                authorization_ticket="",
            )

    def test_claim_batch_returns_batch(self):
        """Claiming a batch returns a valid batch."""
        wf = BackfillWorkflow()

        job = wf.create_backfill_job(
            target_table="responses",
            target_schema_version="we3.response.v2",
            authorization_ticket="ticket_xyz",
        )

        batch = wf.claim_batch(job.job_id, "worker_1")

        assert batch is not None
        assert batch.job_id == job.job_id
        assert batch.offset == 0
        assert batch.limit == job.batch_size

    def test_claim_batch_respects_pause(self):
        """Claim fails when job is paused."""
        wf = BackfillWorkflow()

        job = wf.create_backfill_job(
            target_table="responses",
            target_schema_version="we3.response.v2",
            authorization_ticket="ticket_xyz",
        )
        wf.pause_job(job.job_id)

        batch = wf.claim_batch(job.job_id, "worker_1")

        assert batch is None

    def test_cancel_job_prevents_claim(self):
        """Cancelled jobs cannot claim batches."""
        wf = BackfillWorkflow()

        job = wf.create_backfill_job(
            target_table="responses",
            target_schema_version="we3.response.v2",
            authorization_ticket="ticket_xyz",
        )
        wf.cancel_job(job.job_id)

        batch = wf.claim_batch(job.job_id, "worker_1")

        assert batch is None

    def test_complete_batch_updates_progress(self):
        """Batch completion updates job progress."""
        wf = BackfillWorkflow()

        job = wf.create_backfill_job(
            target_table="responses",
            target_schema_version="we3.response.v2",
            authorization_ticket="ticket_xyz",
        )

        batch = wf.claim_batch(job.job_id, "worker_1")
        checkpoint = wf.complete_batch(batch.batch_id, processed=1000, failed=2)

        assert job.processed_count == 1000
        assert job.failed_count == 2
        assert checkpoint != ""

    def test_reconcile_returns_job_status(self):
        """Reconciliation returns current job status."""
        wf = BackfillWorkflow()

        job = wf.create_backfill_job(
            target_table="responses",
            target_schema_version="we3.response.v2",
            authorization_ticket="ticket_xyz",
        )

        recon = wf.reconcile_job(job.job_id)

        assert recon["job_id"] == job.job_id
        assert recon["state"] == LifecycleState.PENDING.value


class TestBackfillBatch:
    """Tests for backfill batch structure."""

    def test_batch_has_lease_token(self):
        """Batch includes worker lease token."""
        batch = BackfillBatch(
            job_id="job_001",
            offset=1000,
            limit=500,
        )
        assert batch.batch_id != ""
        assert batch.lease_token != ""


class TestRetentionPolicySpec:
    """Tests for retention policy specification."""

    def test_retention_policy_defaults(self):
        """Retention policy has sensible defaults."""
        spec = RetentionPolicySpec(entity_type="response")
        assert spec.policy == RetentionPolicy.AFTER_CERTIFICATION
        assert spec.tombstone_required is True

    def test_retention_policy_serialization(self):
        """Retention policy serializes correctly."""
        spec = RetentionPolicySpec(
            entity_type="classification",
            retention_days=365,
            legal_hold=True,
        )
        d = spec.to_dict()
        assert d["entity_type"] == "classification"
        assert d["legal_hold"] is True


class TestRetentionWorkflow:
    """Tests for retention workflow execution."""

    def test_legal_hold_prevents_deletion(self):
        """Legal hold prevents tombstone creation."""
        wf = RetentionWorkflow()

        policy = RetentionPolicySpec(
            entity_type="response",
            policy=RetentionPolicy.LEGAL_HOLD,
            legal_hold=True,
        )
        wf.set_policy(policy)

        tombstone = wf.apply_retention_policy(
            entity_id="resp_001",
            entity_type="response",
            project_id="proj_test",
            classification="internal",
            retention_hash="abc123",
        )

        assert tombstone is None

    def test_retention_creates_tombstone(self):
        """Retention policy creates tombstone for deletion."""
        wf = RetentionWorkflow()

        policy = RetentionPolicySpec(
            entity_type="response",
            policy=RetentionPolicy.AFTER_CERTIFICATION,
            retention_days=90,
            legal_hold=False,
        )
        wf.set_policy(policy)

        tombstone = wf.apply_retention_policy(
            entity_id="resp_001",
            entity_type="response",
            project_id="proj_test",
            classification="confidential",
            retention_hash="abc123def456",
        )

        assert tombstone is not None
        assert tombstone.original_id == "resp_001"
        assert tombstone.entity_type == "response"
        assert tombstone.deletion_action == DeletionAction.TOMBSTONE

    def test_get_tombstone_by_original_id(self):
        """Tombstone can be retrieved by original entity ID."""
        wf = RetentionWorkflow()

        policy = RetentionPolicySpec(
            entity_type="response",
            legal_hold=False,
        )
        wf.set_policy(policy)

        tombstone = wf.apply_retention_policy(
            entity_id="resp_002",
            entity_type="response",
            project_id="proj_test",
            classification="internal",
            retention_hash="hash_xyz",
        )

        retrieved = wf.get_tombstone("resp_002")

        assert retrieved is not None
        assert retrieved.tombstone_id == tombstone.tombstone_id


class TestTombstone:
    """Tests for tombstone structure."""

    def test_tombstone_creation(self):
        """Tombstone captures deletion metadata."""
        ts = Tombstone(
            original_id="resp_001",
            entity_type="response",
            deletion_action=DeletionAction.TOMBSTONE,
            deletion_reason="retention_expired",
            project_id="proj_test",
            classification="confidential",
            previous_hash="hash_before",
        )

        assert ts.tombstone_id != ""
        assert ts.deleted_at != ""
        assert ts.deletion_hash != ""

    def test_tombstone_serialization(self):
        """Tombstone serializes correctly."""
        ts = Tombstone(
            original_id="resp_001",
            entity_type="response",
        )
        d = ts.to_dict()
        assert d["original_id"] == "resp_001"
        assert d["entity_type"] == "response"


class TestRollbackPlan:
    """Tests for rollback plan structure."""

    def test_rollback_plan_defaults(self):
        """Rollback plan has sensible defaults."""
        plan = RollbackPlan(
            target_version="0.1.0",
            from_version="0.2.0",
            rollback_reason="critical_bug",
        )
        assert plan.preserve_new_evidence is True

    def test_rollback_plan_serialization(self):
        """Rollback plan serializes correctly."""
        plan = RollbackPlan(
            target_version="0.1.0",
            from_version="0.2.0",
            rollback_reason="data_corruption",
            preserve_new_evidence=True,
        )
        d = plan.to_dict()
        assert d["target_version"] == "0.1.0"
        assert d["from_version"] == "0.2.0"


class TestRollbackWorkflow:
    """Tests for rollback workflow execution."""

    def test_create_rollback_requires_authorization(self):
        """Rollback creation requires authorization."""
        wf = RollbackWorkflow()

        with pytest.raises(ValueError, match="authorization_ticket"):
            wf.create_rollback_plan(
                target_version="0.1.0",
                from_version="0.2.0",
                rollback_reason="bug",
                authorization_ticket="",
            )

    def test_preserve_evidence_on_rollback(self):
        """Evidence is preserved when configured."""
        wf = RollbackWorkflow()

        plan = wf.create_rollback_plan(
            target_version="0.1.0",
            from_version="0.2.0",
            rollback_reason="major_issue",
            preserve_new_evidence=True,
            authorization_ticket="ticket_rollback",
        )

        hashes = ["hash_001", "hash_002", "hash_003"]
        preserved = wf.preserve_evidence_on_rollback(plan.plan_id, hashes)

        assert len(preserved) == 3
        assert "hash_001" in preserved

    def test_no_preserve_config(self):
        """Evidence not preserved when configured."""
        wf = RollbackWorkflow()

        plan = wf.create_rollback_plan(
            target_version="0.1.0",
            from_version="0.2.0",
            rollback_reason="minor_issue",
            preserve_new_evidence=False,
            authorization_ticket="ticket_rollback",
        )

        hashes = ["hash_001", "hash_002"]
        preserved = wf.preserve_evidence_on_rollback(plan.plan_id, hashes)

        assert len(preserved) == 0


class TestLifecycleAction:
    """Tests for lifecycle action enum."""

    def test_all_actions_defined(self):
        """All required lifecycle actions exist."""
        assert LifecycleAction.REGRADE.value == "regrade"
        assert LifecycleAction.BACKFILL.value == "backfill"
        assert LifecycleAction.RETENTION.value == "retention"
        assert LifecycleAction.DELETION.value == "deletion"
        assert LifecycleAction.ROLLBACK.value == "rollback"


class TestLifecycleState:
    """Tests for lifecycle state enum."""

    def test_all_states_defined(self):
        """All required lifecycle states exist."""
        assert LifecycleState.PENDING.value == "pending"
        assert LifecycleState.RUNNING.value == "running"
        assert LifecycleState.PAUSED.value == "paused"
        assert LifecycleState.COMPLETED.value == "completed"
        assert LifecycleState.FAILED.value == "failed"
        assert LifecycleState.CANCELLED.value == "cancelled"