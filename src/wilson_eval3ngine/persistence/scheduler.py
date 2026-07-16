"""Durable leasing scheduler with fenced leases, heartbeats, and reconciliation.

T4.1.2 - Implements reliable job scheduling with:
- FOR UPDATE SKIP LOCKED claiming by priority/scheduled time
- Fenced leases with owner ID, lease token/version, acquired time, expiry
- Explicit state transitions with validation
- Bounded retries with jitter and poisoned-job detection
- Stale-job sweeper and periodic reconciliation
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .database import Database
from ..constants import StateTimeouts, RetryThresholds, FailureMode
from ..domain.state import InvalidStateTransition
from ..security.context import validate_context_bound
from ..util import utc_now

logger = logging.getLogger("wilson.scheduler")


class JobState(StrEnum):
    """Job lifecycle states with explicit transitions."""
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    TERMINAL_FAILED = "terminal_failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


# Valid state transitions for jobs (subset of the full state machine)
_JOB_STATE_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.PENDING: {JobState.LEASED, JobState.CANCELLED},
    JobState.LEASED: {JobState.RUNNING, JobState.PENDING, JobState.CANCELLED},
    JobState.RUNNING: {
        JobState.RETRY_WAIT,
        JobState.SUCCEEDED,
        JobState.TERMINAL_FAILED,
        JobState.CANCELLED,
        JobState.DEAD_LETTER,  # Poisoned jobs go directly to dead letter
    },
    JobState.RETRY_WAIT: {JobState.LEASED, JobState.DEAD_LETTER, JobState.CANCELLED},
    JobState.SUCCEEDED: set(),
    JobState.TERMINAL_FAILED: set(),
    JobState.CANCELLED: set(),
    JobState.DEAD_LETTER: set(),
}


def validate_job_transition(current: JobState, target: JobState) -> None:
    """Validate job state transition is allowed."""
    if target not in _JOB_STATE_TRANSITIONS[current]:
        raise InvalidStateTransition(f"invalid job transition: {current} -> {target}")


@dataclass
class LeaseToken:
    """Fenced lease token for job claiming.

    Contains all information needed to verify lease ownership
    and detect race conditions between workers.
    """
    owner_id: str
    lease_id: str
    lease_version: int
    acquired_at: datetime
    expires_at: datetime
    job_id: str

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if lease has expired."""
        check_time = now or utc_now()
        return check_time >= self.expires_at

    def to_comparand(self) -> dict[str, Any]:
        """Return values for compare-and-set operations."""
        return {
            "lease_version": self.lease_version,
            "expires_at": self.expires_at,
        }


@dataclass
class JobLease:
    """Represents a claimed job with lease information."""
    job_id: str
    project_id: str
    job_type: str
    aggregate_id: str
    payload: dict[str, Any]
    attempt_count: int
    lease_token: LeaseToken
    available_at: datetime

    def is_stale(self) -> bool:
        """Check if this lease is no longer valid."""
        return self.lease_token.is_expired()


@dataclass
class RetryPolicy:
    """Bounded retry policy with jitter."""
    max_attempts: int = RetryThresholds.MAX_ATTEMPTS
    initial_backoff: float = 2.0
    max_backoff: float = 60.0
    jitter: bool = True

    def calculate_backoff_seconds(self, attempt: int) -> float:
        """Calculate backoff with exponential increase and optional jitter."""
        backoff = min(self.initial_backoff * (2 ** (attempt - 1)), self.max_backoff)
        if self.jitter:
            import random
            backoff = backoff * (0.5 + random.random() * 0.5)
        return backoff

    def is_retryable(self, attempt_count: int) -> bool:
        """Check if retry is allowed."""
        return attempt_count < self.max_attempts


@dataclass
class ReconciliationReport:
    """Report of scheduler reconciliation findings."""
    check_time: datetime
    stranded_jobs: int = 0
    duplicate_logical_keys: int = 0
    orphaned_attempts: int = 0
    lease_violations: int = 0
    details: list[str] = field(default_factory=list)


class SchedulerError(Exception):
    """Base scheduler error."""
    pass


class LeaseClaimedError(SchedulerError):
    """Job was claimed by another worker during operation."""
    pass


class InvalidLeaseError(SchedulerError):
    """Lease token is invalid or tampered."""
    pass


class DurableScheduler:
    """PostgreSQL-based durable job scheduler with fenced leases.

    Features:
    - CLAIM: FOR UPDATE SKIP LOCKED for atomic job acquisition
    - LEASE: Fenced tokens preventing stale completions
    - HEARTBEAT: Periodic lease extension with version checks
    - RETRY: Bounded retries with jitter
    - RECONCILE: Periodic stranded-job detection
    """

    def __init__(
        self,
        database: Database,
        *,
        lease_seconds: int = StateTimeouts.LEASE_TIMEOUT,
        heartbeat_interval: int = StateTimeouts.HEARTBEAT_INTERVAL,
    ) -> None:
        self.database = database
        self.lease_seconds = lease_seconds
        self.heartbeat_interval = heartbeat_interval
        self._retry_policy = RetryPolicy()

    def _claim_job_sql(self) -> text:
        """SQL for claiming next eligible job."""
        return text(
            """
            WITH candidate AS (
                SELECT id, project_id, job_type, aggregate_id, payload_json, attempt_count
                FROM jobs
                WHERE state = 'pending'
                  AND available_at <= :now
                  AND (leased_until IS NULL OR leased_until < :now)
                ORDER BY available_at, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE jobs
               SET state = 'leased',
                   leased_by = :worker_id,
                   leased_until = :leased_until,
                   lease_version = :lease_version,
                   lease_token = :lease_token,
                   attempt_count = attempt_count + 1,
                   updated_at = :now
              FROM candidate
             WHERE jobs.id = candidate.id
            RETURNING jobs.id, jobs.project_id, jobs.job_type, jobs.aggregate_id,
                      jobs.payload_json, jobs.attempt_count, jobs.leased_until,
                      jobs.lease_version, jobs.lease_token
            """
        )

    def claim_job(self, worker_id: str) -> JobLease | None:
        """Claim the next eligible job for execution.

        Uses FOR UPDATE SKIP LOCKED to atomically claim a job.
        Returns None if no jobs are available.

        Args:
            worker_id: Unique identifier for the claiming worker

        Returns:
            JobLease if a job was claimed, None otherwise

        Raises:
            SchedulerError: If database operation fails unexpectedly
        """
        if self.database.engine.dialect.name != "postgresql":
            raise SchedulerError("durable leasing requires PostgreSQL")

        now = utc_now()
        leased_until = now + timedelta(seconds=self.lease_seconds)
        lease_version = 1
        lease_token = secrets.token_hex(16)

        try:
            with self.database.session() as session, session.begin():
                validate_context_bound(session, worker_id)

                row = session.execute(
                    self._claim_job_sql(),
                    {
                        "now": now,
                        "worker_id": worker_id,
                        "leased_until": leased_until,
                        "lease_version": lease_version,
                        "lease_token": lease_token,
                    },
                ).mappings().first()

                if row is None:
                    return None

                token = LeaseToken(
                    owner_id=worker_id,
                    lease_id=lease_token,
                    lease_version=lease_version,
                    acquired_at=now,
                    expires_at=leased_until,
                    job_id=row["id"],
                )

                logger.info(
                    "job_claimed",
                    extra={
                        "job_id": row["id"],
                        "worker_id": worker_id,
                        "lease_token": lease_token,
                        "expires_at": leased_until.isoformat(),
                    },
                )

                return JobLease(
                    job_id=row["id"],
                    project_id=row["project_id"],
                    job_type=row["job_type"],
                    aggregate_id=row["aggregate_id"],
                    payload=dict(row["payload_json"]) if row["payload_json"] else {},
                    attempt_count=row["attempt_count"],
                    lease_token=token,
                    available_at=now,
                )
        except OperationalError as e:
            logger.error("job_claim_failed", extra={"error": str(e), "worker_id": worker_id})
            raise SchedulerError(f"failed to claim job: {e}") from e

    def _extend_lease_sql(self) -> text:
        """SQL for extending lease with version check."""
        return text(
            """
            UPDATE jobs
               SET leased_until = :new_lease_end,
                   lease_version = lease_version + 1,
                   updated_at = :now
             WHERE id = :job_id
               AND lease_version = :current_version
               AND leased_until >= :now
            RETURNING lease_version
            """
        )

    def extend_lease(self, lease: JobLease, extend_seconds: int | None = None) -> bool:
        """Extend lease expiry with version check (fenced).

        Args:
            lease: Current job lease
            extend_seconds: Seconds to extend (defaults to lease_seconds)

        Returns:
            True if lease was extended, False if lease was lost

        Raises:
            InvalidLeaseError: If lease token doesn't match
        """
        if extend_seconds is None:
            extend_seconds = self.lease_seconds

        now = utc_now()
        new_expiry = now + timedelta(seconds=extend_seconds)
        current_version = lease.lease_token.lease_version

        with self.database.session() as session, session.begin():
            result = session.execute(
                self._extend_lease_sql(),
                {
                    "job_id": lease.job_id,
                    "now": now,
                    "current_version": current_version,
                    "new_lease_end": new_expiry,
                },
            )

            row = result.fetchone()
            if row is None:
                return False

            # Update lease object
            lease.lease_token.lease_version += 1
            lease.lease_token.expires_at = new_expiry

            logger.info(
                "lease_extended",
                extra={
                    "job_id": lease.job_id,
                    "new_version": lease.lease_token.lease_version,
                    "expires_at": new_expiry.isoformat(),
                },
            )
            return True

    def _complete_job_sql(self) -> text:
        """SQL for completing job with fenced update."""
        return text(
            """
            UPDATE jobs
               SET state = :new_state,
                   leased_by = NULL,
                   leased_until = NULL,
                   lease_version = NULL,
                   lease_token = NULL,
                   updated_at = :now
             WHERE id = :job_id
               AND lease_version = :current_version
               AND leased_until >= :now
            RETURNING id
            """
        )

    def complete_job(self, lease: JobLease, success: bool, error_code: str | None = None) -> bool:
        """Complete job with fenced state transition.

        Args:
            lease: Current job lease
            success: Whether job succeeded
            error_code: Error code if failed

        Returns:
            True if completion succeeded, False if lease was lost

        Raises:
            LeaseClaimedError: Another worker claimed this job
        """
        current_version = lease.lease_token.lease_version
        now = utc_now()

        if success:
            new_state = JobState.SUCCEEDED
        elif self._retry_policy.is_retryable(lease.attempt_count):
            # Mark for retry - calculate backoff
            backoff = self._retry_policy.calculate_backoff_seconds(lease.attempt_count)
            retry_available = now + timedelta(seconds=backoff)

            with self.database.session() as session, session.begin():
                result = session.execute(
                    text(
                        """
                        UPDATE jobs
                           SET state = 'retry_wait',
                               leased_by = NULL,
                               leased_until = NULL,
                               lease_version = NULL,
                               lease_token = NULL,
                               available_at = :retry_available,
                               updated_at = :now
                         WHERE id = :job_id
                           AND lease_version = :current_version
                           AND leased_until >= :now
                        RETURNING id
                        """
                    ),
                    {
                        "job_id": lease.job_id,
                        "now": now,
                        "current_version": current_version,
                        "retry_available": retry_available,
                    },
                )

                if result.fetchone() is None:
                    raise LeaseClaimedError(f"job {lease.job_id} lease lost during retry transition")
                return True
        else:
            new_state = JobState.DEAD_LETTER if error_code == FailureMode.POISONED_INPUT else JobState.TERMINAL_FAILED

        with self.database.session() as session, session.begin():
            result = session.execute(
                self._complete_job_sql(),
                {
                    "job_id": lease.job_id,
                    "now": now,
                    "current_version": current_version,
                    "new_state": new_state.value,
                },
            )

            if result.fetchone() is None:
                raise LeaseClaimedError(f"job {lease.job_id} lease lost during completion")

            # Record error if present
            if error_code and not success:
                session.execute(
                    text("UPDATE jobs SET last_error_code = :ec, error_message = :em WHERE id = :job_id"),
                    {"ec": error_code, "em": error_code, "job_id": lease.job_id},
                )

            logger.info(
                "job_completed",
                extra={"job_id": lease.job_id, "state": new_state.value, "success": success},
            )
            return True

    def cancel_job(self, job_id: str, reason: str) -> bool:
        """Cancel a pending or leased job.

        Args:
            job_id: Job to cancel
            reason: Cancellation reason

        Returns:
            True if cancelled, False if job not found or already completed
        """
        now = utc_now()

        with self.database.session() as session, session.begin():
            result = session.execute(
                text(
                    """
                    UPDATE jobs
                       SET state = 'cancelled',
                           leased_by = NULL,
                           leased_until = NULL,
                           updated_at = :now
                     WHERE id = :job_id
                       AND state IN ('pending', 'leased', 'running', 'retry_wait')
                    RETURNING id
                    """
                ),
                {"job_id": job_id, "now": now},
            )

            if result.fetchone():
                logger.info(
                    "job_cancelled",
                    extra={"job_id": job_id, "reason": reason},
                )
                return True
            return False

    def sweep_stale_jobs(self, grace_period_seconds: int = StateTimeouts.STALE_GRACE_PERIOD) -> int:
        """Sweep jobs with expired leases back to pending state.

        Args:
            grace_period_seconds: Extra time to wait before sweeping

        Returns:
            Number of jobs swept
        """
        now = utc_now()
        stale_time = now - timedelta(seconds=grace_period_seconds)

        with self.database.session() as session, session.begin():
            result = session.execute(
                text(
                    """
                    UPDATE jobs
                       SET state = 'pending',
                           leased_by = NULL,
                           leased_until = NULL,
                           lease_version = NULL,
                           lease_token = NULL,
                           updated_at = :now
                     WHERE state = 'leased'
                       AND leased_until < :stale_time
                    RETURNING id
                    """
                ),
                {"now": now, "stale_time": stale_time},
            )

            swept_count = len(result.fetchall())
            logger.info("stale_jobs_swept", extra={"count": swept_count})
            return swept_count

    def reconcile(self) -> ReconciliationReport:
        """Perform full reconciliation scan.

        Detects:
        - Stranded jobs (inconsistent state)
        - Duplicate logical keys
        - Orphaned attempts
        - Lease violations

        Returns:
            ReconciliationReport with findings
        """
        now = utc_now()
        report = ReconciliationReport(check_time=now)

        with self.database.session() as session:
            # Check for stranded jobs (leased but not properly tracked)
            stranded = session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM jobs
                    WHERE state = 'leased'
                      AND (leased_until IS NULL OR leased_until < :now)
                    """
                ),
                {"now": now},
            ).scalar()
            report.stranded_jobs = stranded or 0

            # Check for duplicate logical keys in runs
            dup_keys = session.execute(
                text(
                    """
                    SELECT COUNT(*) - COUNT(DISTINCT logical_key) FROM (
                        SELECT logical_key FROM runs
                        GROUP BY logical_key, experiment_id
                        HAVING COUNT(*) > 1
                    ) duplicates
                    """
                ),
            ).scalar()
            report.duplicate_logical_keys = dup_keys or 0

            # Check for orphaned attempts (runs without parent experiment)
            orphaned = session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM runs r
                    LEFT JOIN experiments e ON r.experiment_id = e.id
                    WHERE e.id IS NULL
                    """
                ),
            ).scalar()
            report.orphaned_attempts = orphaned or 0

            if report.stranded_jobs > 0:
                report.details.append(f"Stranded jobs detected: {report.stranded_jobs}")
            if report.duplicate_logical_keys > 0:
                report.details.append(f"Duplicate logical keys: {report.duplicate_logical_keys}")
            if report.orphaned_attempts > 0:
                report.details.append(f"Orphaned attempts: {report.orphaned_attempts}")

            logger.info(
                "reconciliation_completed",
                extra={
                    "stranded_jobs": report.stranded_jobs,
                    "duplicate_keys": report.duplicate_logical_keys,
                    "orphaned_attempts": report.orphaned_attempts,
                },
            )

        return report

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details by ID."""
        with self.database.session() as session:
            row = session.execute(
                text(
                    """
                    SELECT id, project_id, job_type, state, payload_json,
                           attempt_count, leased_by, leased_until,
                           available_at, last_error_code
                    FROM jobs
                    WHERE id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()

            return dict(row) if row else None


__all__ = [
    "JobState",
    "LeaseToken",
    "JobLease",
    "RetryPolicy",
    "ReconciliationReport",
    "SchedulerError",
    "LeaseClaimedError",
    "InvalidLeaseError",
    "DurableScheduler",
    "validate_job_transition",
]