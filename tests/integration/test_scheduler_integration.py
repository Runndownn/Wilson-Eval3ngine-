"""Integration tests for durable scheduler with PostgreSQL.

T4.1.2 - Integration tests for scheduler behavior.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

from wilson_eval3ngine.persistence.scheduler import (
    DurableScheduler,
    JobState,
    validate_job_transition,
)
from wilson_eval3ngine.persistence.database import Database, Repository
from wilson_eval3ngine.domain.enums import ExperimentState, RunState
from wilson_eval3ngine.util import new_id


@pytest.fixture
def scheduler_db():
    """Create an in-memory SQLite database for scheduler tests."""
    # Note: Full PostgreSQL tests require actual PostgreSQL instance
    db = Database(url="sqlite:///:memory:")
    db.initialize()
    return db


class TestSchedulerIntegration:
    """Integration tests for scheduler with database."""

    def test_claim_job_sql_structure(self, scheduler_db) -> None:
        """Verify claim job SQL uses SKIP LOCKED correctly."""
        scheduler = DurableScheduler(scheduler_db)
        sql = scheduler._claim_job_sql()

        # Verify key clauses exist
        sql_str = str(sql)
        assert "FOR UPDATE SKIP LOCKED" in sql_str
        assert "state = 'pending'" in sql_str
        assert "WHERE jobs.id = candidate.id" in sql_str

    def test_lease_extension_sql_structure(self, scheduler_db) -> None:
        """Verify lease extension uses version check."""
        scheduler = DurableScheduler(scheduler_db)
        sql = scheduler._extend_lease_sql()
        sql_str = str(sql)

        assert "lease_version = :current_version" in sql_str
        assert "RETURNING lease_version" in sql_str

    def test_completion_sql_uses_fencing(self, scheduler_db) -> None:
        """Verify job completion uses lease version fencing."""
        scheduler = DurableScheduler(scheduler_db)
        sql = scheduler._complete_job_sql()
        sql_str = str(sql)

        assert "lease_version = :current_version" in sql_str
        assert "leased_until >= :now" in sql_str


class TestStateTransitions:
    """Test all valid state transitions."""

    def test_all_transitions_valid(self) -> None:
        """Verify all documented transitions work correctly."""
        # Pending transitions
        validate_job_transition(JobState.PENDING, JobState.LEASED)
        validate_job_transition(JobState.PENDING, JobState.CANCELLED)

        # Leased transitions
        validate_job_transition(JobState.LEASED, JobState.RUNNING)
        validate_job_transition(JobState.LEASED, JobState.PENDING)
        validate_job_transition(JobState.LEASED, JobState.CANCELLED)

        # Running transitions
        validate_job_transition(JobState.RUNNING, JobState.RETRY_WAIT)
        validate_job_transition(JobState.RUNNING, JobState.SUCCEEDED)
        validate_job_transition(JobState.RUNNING, JobState.TERMINAL_FAILED)
        validate_job_transition(JobState.RUNNING, JobState.CANCELLED)
        validate_job_transition(JobState.RUNNING, JobState.DEAD_LETTER)

        # Retry wait transitions
        validate_job_transition(JobState.RETRY_WAIT, JobState.LEASED)
        validate_job_transition(JobState.RETRY_WAIT, JobState.DEAD_LETTER)
        validate_job_transition(JobState.RETRY_WAIT, JobState.CANCELLED)

    def test_terminal_states_no_outgoing(self) -> None:
        """Terminal states should have no outgoing transitions."""
        for state in [JobState.SUCCEEDED, JobState.TERMINAL_FAILED, JobState.CANCELLED, JobState.DEAD_LETTER]:
            with pytest.raises(Exception):  # InvalidStateTransition
                validate_job_transition(state, JobState.RUNNING)


class TestRetryPolicyIntegration:
    """Test retry policy in scheduler context."""

    def test_retry_policy_default_from_constants(self, scheduler_db) -> None:
        """Scheduler retry policy matches constants."""
        from wilson_eval3ngine.constants import RetryThresholds

        scheduler = DurableScheduler(scheduler_db)
        # Default max attempts from RetryThresholds
        assert scheduler._retry_policy.max_attempts == RetryThresholds.MAX_ATTEMPTS


class TestReconciliationQueries:
    """Test reconciliation SQL queries."""

    def test_reconcile_finds_stranded_jobs(self, scheduler_db) -> None:
        """Verify reconciliation detects stranded jobs."""
        db = scheduler_db
        repo = Repository(db)
        repo.ensure_project("test_project")

        # Create a leased job that's past expiry
        with db.session() as session, session.begin():
            past_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
            session.execute(
                text(
                    """
                    INSERT INTO jobs (id, project_id, job_type, aggregate_id, payload_json, state, leased_until, available_at, created_at, updated_at, attempt_count)
                    VALUES ('job_stale', 'test_project', 'test', 'agg', '{}', 'leased', :past, :past, :past, :past, 0)
                    """
                ),
                {"past": past_time},
            )

        # Run reconciliation
        scheduler = DurableScheduler(db)
        report = scheduler.reconcile()

        # Should detect stranded job
        assert report.stranded_jobs >= 1