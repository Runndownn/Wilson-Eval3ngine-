"""Transactional outbox pattern for reliable event emission.

T3.1.4 - Provenance, transactional outbox, and audit linkage.
Ensures domain changes and emitted events cannot diverge.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from ..util import canonical_json, new_id, sha256_hex, utc_now

logger = logging.getLogger("wilson.persistence.outbox")


class OutboxEventType(StrEnum):
    """Event types for the outbox."""
    EXPERIMENT_CREATED = "experiment.created"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    CLASSIFICATION_RECORDED = "classification.recorded"
    GATE_EVALUATED = "gate.evaluated"
    DOSSIER_GENERATED = "dossier.generated"


@dataclass(frozen=True)
class OutboxEvent:
    """Event envelope for outbox pattern.

    Fields follow the event-carried state pattern to ensure auditable,
    idempotent event processing.
    """
    event_id: str
    aggregate_id: str
    aggregate_type: str
    project_id: str
    event_type: str
    schema_version: str = "we3.outbox_event.v1"
    occurred_at: str = field(default_factory=lambda: utc_now().isoformat())
    recorded_at: str = field(default_factory=lambda: utc_now().isoformat())
    producer_version: str = "1.0.0"
    payload_hash: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""

    def __post_init__(self) -> None:
        # Compute payload hash for integrity
        if not self.payload_hash:
            object.__setattr__(self, 'payload_hash', sha256_hex(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "project_id": self.project_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "producer_version": self.producer_version,
            "payload_hash": self.payload_hash,
            "payload": self.payload,
            "trace_id": self.trace_id or self.event_id,
        }


class OutboxRow(Base):
    """Persistent outbox table for transactional event storage.

    Events are written in the same transaction as domain state changes,
    ensuring atomicity between data changes and event emission.
    """
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_project_status", "project_id", "status"),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_outbox_event_type", "event_type"),
        Index("ix_outbox_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_id: Mapped[str] = mapped_column(String(96), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(String, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default="we3.outbox_event.v1")
    producer_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False)
    trace_id: Mapped[str] = mapped_column(String(96), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)


class Outbox:
    """Transactional outbox for event emission.

    Usage:
        outbox = Outbox(database)
        with database.session.begin():
            # ... domain changes ...
            outbox.enqueue(OutboxEvent(...))
        # On commit, event is available for consumption
    """

    def __init__(self, database) -> None:
        self.database = database

    def enqueue(self, event: OutboxEvent) -> str:
        """Enqueue an event within the current transaction.

        Args:
            event: The event to enqueue

        Returns:
            The event_id for reference
        """
        with self.database.session() as session:
            session.add(OutboxRow(
                id=new_id("outbox"),
                project_id=event.project_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                event_id=event.event_id,
                payload_json=event.payload,
                payload_hash=event.payload_hash,
                schema_version=event.schema_version,
                producer_version=event.producer_version,
                status="pending",
                occurred_at=datetime.fromisoformat(event.occurred_at),
                recorded_at=datetime.fromisoformat(event.recorded_at),
                trace_id=event.trace_id or event.event_id,
            ))
        logger.info(
            "outbox_event_enqueued",
            extra={"event_id": event.event_id, "event_type": event.event_type, "aggregate_id": event.aggregate_id},
        )
        return event.event_id

    def mark_delivered(self, event_id: str) -> None:
        """Mark an event as delivered to external system.

        Args:
            event_id: The event to mark
        """
        with self.database.session() as session, session.begin():
            row = session.get(OutboxRow, event_id)
            if row and row.status == "pending":
                row.status = "delivered"

    def mark_failed(self, event_id: str, error: str) -> None:
        """Mark an event delivery as failed.

        Args:
            event_id: The event to mark
            error: Error description for retry or dead-letter queue
        """
        with self.database.session() as session, session.begin():
            row = session.get(OutboxRow, event_id)
            if row:
                row.status = "failed"
                # In production, we'd store the error in a separate field
                logger.error("outbox_event_failed", extra={"event_id": event_id, "error": error})

    def pending_events(self, limit: int = 100) -> list[OutboxEvent]:
        """Fetch pending events for delivery.

        Args:
            limit: Maximum number of events to fetch

        Returns:
            List of pending events
        """
        with self.database.session() as session:
            rows = session.execute(
                text("""
                    SELECT * FROM outbox_events
                    WHERE status = 'pending'
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                """),
                {"limit": limit},
            ).mappings().all()

        return [
            OutboxEvent(
                event_id=row["event_id"],
                aggregate_id=row["aggregate_id"],
                aggregate_type=row["aggregate_type"],
                project_id=row["project_id"],
                event_type=row["event_type"],
                schema_version=row["schema_version"],
                occurred_at=row["occurred_at"].isoformat() if isinstance(row["occurred_at"], datetime) else row["occurred_at"],
                recorded_at=row["recorded_at"].isoformat() if isinstance(row["recorded_at"], datetime) else row["recorded_at"],
                producer_version=row["producer_version"],
                payload_hash=row["payload_hash"],
                payload=row["payload_json"],
                trace_id=row["trace_id"],
            )
            for row in rows
        ]


__all__ = [
    "OutboxEventType",
    "OutboxEvent",
    "OutboxRow",
    "Outbox",
]