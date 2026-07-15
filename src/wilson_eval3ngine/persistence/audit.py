from __future__ import annotations

from datetime import timezone
from typing import Any

from sqlalchemy import select

from .database import AuditEventRow, Database
from ..util import new_id, sha256_hex, utc_now


def _timestamp_token(value):
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


class AuditLedger:
    """Append-only hash-linked audit metadata ledger.

    Production deployments should additionally sign checkpoints and export them
    to an independently controlled retention location.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

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
        with self.database.session() as session, session.begin():
            previous = session.scalar(
                select(AuditEventRow)
                .where(AuditEventRow.project_id == project_id)
                .order_by(AuditEventRow.created_at.desc(), AuditEventRow.id.desc())
                .limit(1)
            )
            previous_hash = previous.event_hash if previous else None
            event_id = new_id("audit")
            occurred_at = utc_now()
            event_hash = sha256_hex(
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
        previous_hash: str | None = None
        for row in rows:
            expected = sha256_hex(
                {
                    "event_id": row.id,
                    "project_id": row.project_id,
                    "event_type": row.event_type,
                    "aggregate_type": row.aggregate_type,
                    "aggregate_id": row.aggregate_id,
                    "actor_id": row.actor_id,
                    "payload": row.payload_json,
                    "previous_hash": previous_hash,
                    "occurred_at": _timestamp_token(row.created_at),
                }
            )
            if row.previous_hash != previous_hash or row.event_hash != expected:
                return False
            previous_hash = row.event_hash
        return True
