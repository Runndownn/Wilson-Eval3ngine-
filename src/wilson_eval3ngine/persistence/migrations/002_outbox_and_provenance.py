"""Outbox events and provenance edges tables.

Revision ID: 002_outbox_and_provenance
Revises: 001_initial_core_schema
Create Date: 2026-07-15

Prerequisites: 001_initial_core_schema
Lock Risk: LOW - table creation with foreign keys
Compatible Application Versions: >=0.2.0

Creates outbox_events table for transactional event emission and
provenance_edges table for immutable chain linkage.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_outbox_and_provenance"
down_revision = "001_initial_core_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create outbox and provenance tables."""
    # Outbox events table - transactional event storage
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("event_id", sa.String(96), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False, server_default="we3.outbox_event.v1"),
        sa.Column("producer_version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_id", sa.String(96), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_outbox_id_not_empty"),
        sa.CheckConstraint("status IN ('pending', 'delivered', 'failed')", name="ck_outbox_status_valid"),
        sa.Index("ix_outbox_project_status", "project_id", "status"),
        sa.Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
        sa.Index("ix_outbox_event_type", "event_type"),
        sa.Index("ix_outbox_created", "created_at"),
    )

    # Provenance edges table - immutable chain linkage
    op.create_table(
        "provenance_edges",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_version", sa.String(64), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_version", sa.String(64), nullable=False),
        sa.Column("target_hash", sa.String(64), nullable=False),
        sa.Column("edge_type", sa.String(64), nullable=False),
        sa.Column("edge_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_provenance_id_not_empty"),
        sa.Index("ix_provenance_source", "source_type", "source_id"),
        sa.Index("ix_provenance_target", "target_type", "target_id"),
        sa.Index("ix_provenance_edge_type", "edge_type"),
        sa.Index("ix_provenance_edge_hash", "edge_hash"),
    )

    # Add RLS policies for outbox_events and provenance_edges
    op.execute("ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE provenance_edges ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY outbox_events_project_isolation ON outbox_events
        USING (project_id = current_setting('we3.project_id', true))
        WITH CHECK (project_id = current_setting('we3.project_id', true))
    """)

    op.execute("""
        CREATE POLICY provenance_edges_project_isolation ON provenance_edges
        USING (project_id = current_setting('we3.project_id', true))
        WITH CHECK (project_id = current_setting('we3.project_id', true))
    """)


def downgrade() -> None:
    """Drop outbox and provenance tables."""
    op.execute("DROP POLICY IF EXISTS provenance_edges_project_isolation ON provenance_edges")
    op.execute("DROP POLICY IF EXISTS outbox_events_project_isolation ON outbox_events")

    op.drop_table("provenance_edges")
    op.drop_table("outbox_events")