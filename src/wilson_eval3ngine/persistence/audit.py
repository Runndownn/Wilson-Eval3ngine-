from __future__ import annotations

import hashlib
import threading
from collections import defaultdict
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Protocol

from sqlalchemy import select, text

from .database import AuditEventRow, Database
from ..util import new_id, sha256_hex, utc_now


def _coerce_utc(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("audit timestamp must be a datetime or ISO timestamp")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp_token(value: Any) -> str:
    return _coerce_utc(value).replace(tzinfo=None).isoformat(timespec="microseconds")


class AuditRecord(Protocol):
    id: str
    project_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    actor_id: str
    payload_json: dict[str, Any]
    previous_hash: str | None
    event_hash: str
    created_at: Any


def compute_audit_event_hash(
    *,
    event_id: str,
    project_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_id: str,
    payload: dict[str, Any],
    previous_hash: str | None,
    occurred_at: Any,
) -> str:
    """Compute the one canonical audit hash used by write and verification."""
    return sha256_hex(
        {
            "event_id": event_id,
            "project_id": project_id,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "actor_id": actor_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "occurred_at": _timestamp_token(occurred_at),
        }
    )


def verify_audit_records(rows: Iterable[AuditRecord]) -> bool:
    previous_hash: str | None = None
    for row in rows:
        expected = compute_audit_event_hash(
            event_id=row.id,
            project_id=row.project_id,
            event_type=row.event_type,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            actor_id=row.actor_id,
            payload=row.payload_json,
            previous_hash=previous_hash,
            occurred_at=row.created_at,
        )
        if row.previous_hash != previous_hash or row.event_hash != expected:
            return False
        previous_hash = row.event_hash
    return True


def _project_advisory_key(project_id: str) -> int:
    """Map project identity to PostgreSQL's signed 64-bit advisory-lock key."""
    digest = hashlib.sha256(project_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class AuditLedger:
    """Append-only, hash-linked, project-serialized audit metadata ledger.

    PostgreSQL appends acquire a transaction-scoped advisory lock derived from
    project identity before reading the current tail. This prevents two workers
    from deriving the same ``previous_hash`` and forking the chain. The local
    SQLite lane uses a process-local project lock; multi-process assurance is a
    PostgreSQL responsibility.

    Production deployments should additionally sign/export checkpoints to an
    independently controlled retention location.
    """

    _local_locks_guard = threading.Lock()
    _local_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def __init__(self, database: Database) -> None:
        self.database = database

    @classmethod
    def _local_project_lock(cls, project_id: str) -> threading.Lock:
        with cls._local_locks_guard:
            return cls._local_locks[project_id]

    def append(
        self,
        *,
        project_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> str:
        with self.database.session() as session:
            dialect = session.get_bind().dialect.name
            local_guard = (
                self._local_project_lock(project_id)
                if dialect == "sqlite"
                else nullcontext()
            )
            with local_guard, session.begin():
                if dialect == "postgresql":
                    session.execute(
                        text("SELECT pg_advisory_xact_lock(:lock_key)"),
                        {"lock_key": _project_advisory_key(project_id)},
                    )

                previous = session.scalar(
                    select(AuditEventRow)
                    .where(AuditEventRow.project_id == project_id)
                    .order_by(
                        AuditEventRow.created_at.desc(),
                        AuditEventRow.id.desc(),
                    )
                    .limit(1)
                )
                previous_hash = previous.event_hash if previous else None
                event_id = new_id("audit")
                occurred_at = utc_now()
                if previous is not None:
                    previous_time = _coerce_utc(previous.created_at)
                    if occurred_at <= previous_time:
                        # Verification orders by timestamp + id. A strictly
                        # increasing timestamp makes the hash-chain order stable
                        # even if two appends happen inside one clock microsecond.
                        occurred_at = previous_time + timedelta(microseconds=1)

                event_hash = compute_audit_event_hash(
                    event_id=event_id,
                    project_id=project_id,
                    event_type=event_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    actor_id=actor_id,
                    payload=payload,
                    previous_hash=previous_hash,
                    occurred_at=occurred_at,
                )
                session.add(
                    AuditEventRow(
                        id=event_id,
                        project_id=project_id,
                        event_type=event_type,
                        aggregate_type=aggregate_type,
                        aggregate_id=aggregate_id,
                        actor_id=actor_id,
                        payload_json=payload,
                        previous_hash=previous_hash,
                        event_hash=event_hash,
                        created_at=occurred_at,
                    )
                )
                session.flush()
                return event_hash

    def verify(self, project_id: str) -> bool:
        with self.database.session() as session:
            rows = list(
                session.scalars(
                    select(AuditEventRow)
                    .where(AuditEventRow.project_id == project_id)
                    .order_by(AuditEventRow.created_at, AuditEventRow.id)
                )
            )
        return verify_audit_records(rows)


__all__ = [
    "AuditLedger",
    "compute_audit_event_hash",
    "verify_audit_records",
]
