"""Backup and recovery tables for evidence preservation.

Revision ID: 006_backup_and_recovery
Revises: 005_review_governance_schema
Create Date: 2026-07-17

Prerequisites: 005_review_governance_schema
Lock Risk: LOW - table creation with indices
Compatible Application Versions: >=0.3.0

Adds tables for:
- backup_metadata: Tracks backup operations and integrity
- restore_plans: Point-in-time restore planning
- reconciliation_reports: Post-restore verification
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006_backup_and_recovery"
down_revision = "005_review_governance_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create backup and recovery tables."""
    # Backup metadata table
    op.create_table(
        "backup_metadata",
        sa.Column("backup_id", sa.String(96), primary_key=True),
        sa.Column("backup_type", sa.String(32), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backup_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("wal_start_lsn", sa.String(32)),
        sa.Column("wal_end_lsn", sa.String(32)),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("key_id", sa.String(255), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_ref", sa.String(255), nullable=False),
        sa.CheckConstraint("length(backup_id) > 0", name="ck_backup_id_not_empty"),
        sa.CheckConstraint(
            "backup_type IN ('full', 'incremental', 'wal', 'pitr')",
            name="ck_backup_type_valid",
        ),
        sa.Index("ix_backup_timestamp", "backup_timestamp"),
        sa.Index("ix_backup_type", "backup_type"),
    )

    # Restore plans table
    op.create_table(
        "restore_plans",
        sa.Column("plan_id", sa.String(96), primary_key=True),
        sa.Column("target_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backup_sequence", postgresql.JSONB(), nullable=False),
        sa.Column("wal_segments_needed", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_restore_time_minutes", sa.Integer(), nullable=False),
        sa.Column("isolated_environment", sa.String(255), nullable=False),
        sa.Column("plan_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.CheckConstraint("length(plan_id) > 0", name="ck_restore_plan_id_not_empty"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'verified')",
            name="ck_restore_plan_status_valid",
        ),
        sa.Index("ix_restore_plans_target", "target_timestamp"),
    )

    # Reconciliation reports table
    op.create_table(
        "reconciliation_reports",
        sa.Column("report_id", sa.String(96), primary_key=True),
        sa.Column("restored_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_runs", sa.Integer(), nullable=False),
        sa.Column("runs_matched", sa.Integer(), nullable=False),
        sa.Column("runs_missing", sa.Integer(), nullable=False),
        sa.Column("total_classifications", sa.Integer(), nullable=False),
        sa.Column("classifications_matched", sa.Integer(), nullable=False),
        sa.Column("audit_chain_valid", sa.Boolean(), nullable=False),
        sa.Column("outbox_events_pending", sa.Integer(), nullable=False),
        sa.Column("metric_snapshots_matched", sa.Integer(), nullable=False),
        sa.Column("gate_decisions_matched", sa.Integer(), nullable=False),
        sa.Column("provenance_edges_matched", sa.Integer(), nullable=False),
        sa.Column("reconciliation_signature", postgresql.JSONB()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "length(report_id) > 0", name="ck_reconciliation_report_id_not_empty"
        ),
        sa.CheckConstraint(
            "status IN ('pass', 'fail')", name="ck_reconciliation_status_valid"
        ),
        sa.Index("ix_reconciliation_verified", "verified_timestamp"),
    )


def downgrade() -> None:
    """Drop backup and recovery tables."""
    op.drop_table("reconciliation_reports")
    op.drop_table("restore_plans")
    op.drop_table("backup_metadata")