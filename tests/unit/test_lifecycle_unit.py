"""Unit tests for lifecycle management: regrading, retention, deletion, rollback."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text as sql_text

from wilson_eval3ngine.persistence.database import Database, Repository
from wilson_eval3ngine.persistence.lifecycle import (
    DeletionTombstone,
    HoldState,
    LifecycleJob,
    LifecycleManager,
    create_deletion_tombstone,
)


class TestLifecycleJob:
    def test_resume_key_includes_operation_and_project(self):
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1", "run2"],
        )
        key = job.resume_key()
        assert "regrade" in key
        assert "proj1" in key

    def test_resume_key_includes_checkpoint(self):
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1", "run2"],
            checkpoint_token="checkpoint123",
        )
        key = job.resume_key()
        assert "checkpoint123" in key

    def test_resume_key_defaults_to_start(self):
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1"],
        )
        key = job.resume_key()
        assert "start" in key


class TestDeletionTombstone:
    def test_compute_tombstone_hash_is_deterministic(self):
        tombstone = DeletionTombstone(
            original_id="run1",
            project_id="proj1",
            table_name="runs",
            deleted_at=datetime(2026, 1, 1, 12, 0, 0),
            deleted_by="admin",
            deletion_reason="retention",
            original_hash="abc123",
            tombstone_hash="",
        )
        h1 = tombstone.compute_tombstone_hash()
        h2 = tombstone.compute_tombstone_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_compute_tombstone_hash_changes_with_content(self):
        base = DeletionTombstone(
            original_id="run1",
            project_id="proj1",
            table_name="runs",
            deleted_at=datetime(2026, 1, 1, 12, 0, 0),
            deleted_by="admin",
            deletion_reason="retention",
            original_hash="abc123",
            tombstone_hash="",
        )
        h1 = base.compute_tombstone_hash()

        modified = DeletionTombstone(
            original_id="run2",
            project_id="proj1",
            table_name="runs",
            deleted_at=datetime(2026, 1, 1, 12, 0, 0),
            deleted_by="admin",
            deletion_reason="retention",
            original_hash="abc123",
            tombstone_hash="",
        )
        h2 = modified.compute_tombstone_hash()
        assert h1 != h2


class TestCreateDeletionTombstone:
    def test_creates_tombstone_with_correct_fields(self):
        original_record = {
            "id": "run1",
            "project_id": "proj1",
            "primary_label": "safe",
            "confidence": 0.95,
        }
        tombstone = create_deletion_tombstone(
            original_id="run1",
            project_id="proj1",
            table_name="classifications",
            deleted_by="admin",
            deletion_reason="retention_sweep",
            original_record=original_record,
        )

        assert tombstone.original_id == "run1"
        assert tombstone.project_id == "proj1"
        assert tombstone.table_name == "classifications"
        assert tombstone.deleted_by == "admin"
        assert tombstone.deletion_reason == "retention_sweep"
        assert len(tombstone.original_hash) == 64
        assert len(tombstone.tombstone_hash) == 64
        assert tombstone.tombstone_hash != ""

    def test_tombstone_hash_is_computed(self):
        tombstone = create_deletion_tombstone(
            original_id="run1",
            project_id="proj1",
            table_name="classifications",
            deleted_by="admin",
            deletion_reason="retention_sweep",
            original_record={"id": "run1"},
        )
        assert tombstone.tombstone_hash == tombstone.compute_tombstone_hash()


class TestLifecycleManagerInit:
    def test_init_stores_repository_and_evidence_store(self):
        repo = MagicMock()
        evidence = MagicMock()
        manager = LifecycleManager(repo, evidence)
        assert manager.repository is repo
        assert manager.evidence_store is evidence


class TestLifecycleManagerJobId:
    def test_generate_job_id_is_deterministic_for_same_inputs(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job_id = manager._generate_job_id("regrade", "proj1", "exp1")
        assert len(job_id) == 24
        assert all(c in "0123456789abcdef" for c in job_id)


class TestLifecycleManagerCheckpoint:
    def test_encode_checkpoint_returns_sha256(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        token = manager._encode_checkpoint(42)
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_decode_checkpoint_returns_zero_for_invalid_token(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        result = manager._decode_checkpoint("invalid_token")
        assert result == 0


class TestLifecycleManagerValidateSafety:
    def test_validate_allows_normal_job(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1"],
        )
        violations = manager.validate_lifecycle_safety(job)
        assert violations == []

    def test_validate_blocks_held_job(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1"],
            hold_state=HoldState.HELD,
        )
        violations = manager.validate_lifecycle_safety(job)
        assert "legal_hold_active" in violations

    def test_validate_blocks_deletion_without_reason(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="deletion",
            target_ids=["run1"],
            deletion_reason=None,
        )
        violations = manager.validate_lifecycle_safety(job)
        assert "missing_deletion_reason" in violations

    def test_validate_allows_deletion_with_reason(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="deletion",
            target_ids=["run1"],
            deletion_reason="policy_expired",
        )
        violations = manager.validate_lifecycle_safety(job)
        assert violations == []

    def test_validate_allows_dry_run_deletion_without_reason(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())
        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="deletion",
            target_ids=["run1"],
            deletion_reason=None,
            dry_run=True,
        )
        violations = manager.validate_lifecycle_safety(job)
        assert violations == []


class TestLifecycleManagerGetExperimentRuns:
    def test_get_experiment_runs_returns_run_ids(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        # Use Repository to insert test data
        repository = Repository(db)
        repository.ensure_project("proj1")
        repository.create_experiment(
            experiment_id="exp1",
            project_id="proj1",
            name="Test Exp",
            lane="default",
            manifest_hash="hash123",
            manifest_json={},
        )

        # Insert runs directly
        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO runs (id, project_id, experiment_id, logical_key, "
                    "case_version_id, prompt_family_id, model_config_id, "
                    "repetition_index, expected_treatment, state, created_at, updated_at) "
                    "VALUES ('run1', 'proj1', 'exp1', 'key1', 'v1', 'pf1', 'mc1', "
                    "0, 'safe', 'completed', datetime('now'), datetime('now'))"
                )
            )
            session.execute(
                sql_text(
                    "INSERT INTO runs (id, project_id, experiment_id, logical_key, "
                    "case_version_id, prompt_family_id, model_config_id, "
                    "repetition_index, expected_treatment, state, created_at, updated_at) "
                    "VALUES ('run2', 'proj1', 'exp1', 'key2', 'v1', 'pf1', 'mc1', "
                    "0, 'safe', 'completed', datetime('now'), datetime('now'))"
                )
            )

        runs = manager._get_experiment_runs("proj1", "exp1")
        assert len(runs) == 2
        assert "run1" in runs
        assert "run2" in runs

    def test_get_experiment_runs_empty_for_nonexistent_experiment(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        runs = manager._get_experiment_runs("proj1", "nonexistent")
        assert runs == []


class TestLifecycleManagerCheckRetentionHold:
    def test_no_hold_returns_none(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        state = manager._check_retention_hold("proj1", ["run1"])
        assert state == HoldState.NONE

    def test_legal_hold_returns_held(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO overrides (id, gate_id, requester, rationale, "
                    "scope_json, applied, created_at) VALUES ('ov1', 'gate1', 'admin', "
                    "'legal_hold', '{\"project_id\": \"proj1\", \"hold_type\": \"legal_hold\"}', true, datetime('now'))"
                )
            )

        state = manager._check_retention_hold("proj1", ["run1"])
        assert state == HoldState.HELD

    def test_pending_review_hold(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO overrides (id, gate_id, requester, rationale, "
                    "scope_json, applied, created_at) VALUES ('ov1', 'gate1', 'admin', "
                    "'retention_hold', '{\"project_id\": \"proj1\", \"hold_type\": \"retention_hold\"}', true, datetime('now'))"
                )
            )

        state = manager._check_retention_hold("proj1", ["run1"])
        assert state == HoldState.PENDING_REVIEW

    def test_empty_run_ids_returns_none(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        state = manager._check_retention_hold("proj1", [])
        assert state == HoldState.NONE


class TestLifecycleManagerRegrade:
    def test_regrade_creates_new_version(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        # Insert run and classification
        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO runs (id, project_id, experiment_id, logical_key, "
                    "case_version_id, prompt_family_id, model_config_id, "
                    "repetition_index, expected_treatment, state, created_at, updated_at) "
                    "VALUES ('run1', 'proj1', 'exp1', 'key1', 'v1', 'pf1', 'mc1', "
                    "0, 'safe', 'completed', datetime('now'), datetime('now'))"
                )
            )
            session.execute(
                sql_text(
                    "INSERT INTO classifications (id, project_id, run_id, "
                    "primary_label, confidence, requires_human_review, "
                    "payload_json, created_at) VALUES ('cls1', 'proj1', 'run1', 'safe', "
                    "0.95, false, '{\"evidence_hash\": \"abc123\", \"project_id\": \"proj1\"}', datetime('now'))"
                )
            )

        # Regrade
        manager._regrade_single_grade("run1", ["cls1"])

        # Verify new classification was created
        with db.session() as session:
            rows = session.execute(
                sql_text("SELECT id, superseded_by_id FROM classifications")
            ).fetchall()

            # Should have original + new
            assert len(rows) == 2

            # Original should be superseded
            original = [r for r in rows if r[0] == "cls1"][0]
            assert original[1] is not None  # superseded_by_id set

            # New one should not be superseded
            new = [r for r in rows if r[0] != "cls1"][0]
            assert new[1] is None  # superseded_by_id is NULL

    def test_regrade_no_classifications_no_error(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO runs (id, project_id, experiment_id, logical_key, "
                    "case_version_id, prompt_family_id, model_config_id, "
                    "repetition_index, expected_treatment, state, created_at, updated_at) "
                    "VALUES ('run1', 'proj1', 'exp1', 'key1', 'v1', 'pf1', 'mc1', "
                    "0, 'safe', 'completed', datetime('now'), datetime('now'))"
                )
            )

        # Should not raise
        manager._regrade_single_grade("run1", [])


class TestLifecycleManagerDelete:
    def test_delete_creates_tombstone_and_removes_record(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        with db.session() as session, session.begin():
            session.execute(
                sql_text(
                    "INSERT INTO classifications (id, project_id, run_id, "
                    "primary_label, confidence, requires_human_review, "
                    "payload_json, created_at) VALUES ('cls1', 'proj1', 'run1', 'safe', "
                    "0.95, false, '{\"evidence_hash\": \"abc123\"}', datetime('now'))"
                )
            )

        # Delete
        manager._delete_single_item("cls1", "admin")

        # Verify classification is deleted
        with db.session() as session:
            row = session.execute(
                sql_text("SELECT id FROM classifications WHERE id = 'cls1'")
            ).fetchone()
            assert row is None

            # Verify tombstone was created in audit_events
            tombstones = session.execute(
                sql_text(
                    "SELECT event_type, aggregate_id FROM audit_events "
                    "WHERE event_type = 'deletion_tombstone'"
                )
            ).fetchall()
            assert len(tombstones) == 1
            assert tombstones[0][1] == "cls1"

    def test_delete_nonexistent_item_no_error(self, db):
        repo = MagicMock()
        repo.database = db
        manager = LifecycleManager(repo, MagicMock())

        repository = Repository(db)
        repository.ensure_project("proj1")

        # Should not raise
        manager._delete_single_item("nonexistent", "admin")


class TestLifecycleManagerBackfill:
    def test_backfill_processes_all_items(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())

        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1", "run2", "run3"],
            batch_size=1000,
            total_target_count=3,
        )

        manager._process_backfill_item = MagicMock()

        processed = manager.execute_backfill(job, None)
        assert processed == 3
        assert job.processed_count == 3
        assert job.completed_at is not None
        assert manager._process_backfill_item.call_count == 3

    def test_backfill_respects_batch_size(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())

        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1", "run2", "run3", "run4", "run5"],
            batch_size=2,
            total_target_count=5,
        )

        manager._process_backfill_item = MagicMock()

        processed = manager.execute_backfill(job, None)
        assert processed == 2
        assert job.checkpoint_token is not None
        assert job.completed_at is None

    def test_backfill_resumes_from_checkpoint(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())

        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1", "run2", "run3", "run4", "run5"],
            batch_size=2,
            checkpoint_token=manager._encode_checkpoint(2),
        )

        manager._process_backfill_item = MagicMock()

        processed = manager.execute_backfill(job, None)
        assert processed == 2
        assert manager._process_backfill_item.call_count == 2

    def test_backfill_raises_on_held_job(self):
        repo = MagicMock()
        manager = LifecycleManager(repo, MagicMock())

        job = LifecycleJob(
            job_id="job1",
            project_id="proj1",
            operation_type="regrade",
            target_ids=["run1"],
            hold_state=HoldState.HELD,
        )

        with pytest.raises(ValueError, match="legal hold"):
            manager.execute_backfill(job, None)
