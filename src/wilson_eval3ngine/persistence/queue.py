from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import text

from .database import Database
from ..util import utc_now
from ..constants import StateTimeouts


_POSTGRES_LEASE_SQL = text(
    """
    WITH candidate AS (
        SELECT id
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
           attempt_count = attempt_count + 1,
           updated_at = :now
      FROM candidate
     WHERE jobs.id = candidate.id
    RETURNING jobs.id, jobs.project_id, jobs.job_type, jobs.aggregate_id,
              jobs.payload_json, jobs.attempt_count, jobs.leased_until
    """
)


class DurableJobQueue:
    """PostgreSQL leasing queue contract.

    The synchronous foundation runner does not require this queue. It is
    included because durable leasing is the first production orchestration path.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def lease_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = StateTimeouts.LEASE_TIMEOUT,
    ) -> dict[str, Any] | None:
        if self.database.engine.dialect.name != "postgresql":
            raise RuntimeError("durable SKIP LOCKED leasing requires PostgreSQL")
        now = utc_now()
        with self.database.session() as session, session.begin():
            row = session.execute(
                _POSTGRES_LEASE_SQL,
                {
                    "now": now,
                    "worker_id": worker_id,
                    "leased_until": now + timedelta(seconds=lease_seconds),
                },
            ).mappings().first()
            return dict(row) if row else None
