"""Lifecycle workflow tables for regrade, backfill, retention, and rollback.

Revision ID: 003_lifecycle_workflows
Revises: 002_outbox_and_provenance
Create Date: 2026-07-15

Prerequisites: 002_outbox_and_provenance
Lock Risk: LOW - table creation for workflow tracking
Compatible Application Versions: >=0.3.0

Creates tables for:
- regrade_jobs: Track regrade workflow executions
- backfill_jobs: Resumable backfill job specifications and checkpoints
- backfill_batches: Individual batch tracking for parallelization
- retention_policies: Retention policy definitions with legal hold support
- tombstones: Immutable deletion markers
- rollback_plans: Application rollback preservation plans
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_lifecycle_workflows"
down_revision = "002_outbox_and_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create lifecycle workflow tables."""
    # Regrade jobs table - tracks regrade workflow executions
    op.create_table(
        "regrade_jobs",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("run_id", sa.String(96), nullable=False),
        sa.Column("old_rubric_version", sa.String(64), nullable=False),
        sa.Column("new_rubric_version", sa.String(64), nullable=False),
        sa.Column("requester_id", sa.String(96), nullable=False),
        sa.Column("authorization_ticket", sa.String(96), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("classifications_regenerated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metric_snapshots_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("gate_results_recomputed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("previous_audit_hash", sa.String(64), nullable=True),
        sa.Column("current_audit_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) > 0", name="ck_regrade_id_not_empty"),
        sa.CheckConstraint("state IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name="ck_regrade_state_valid"),
        sa.Index("ix_regrade_run_id", "run_id"),
        sa.Index("ix_regrade_state", "state"),
    )

    # Backfill jobs table - resumable backfill job specifications
    op.create_table(
        "backfill_jobs",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("target_schema_version", sa.String(64), nullable=False),
        sa.Column("target_table", sa.String(64), nullable=False),
        sa.Column("where_clause", sa.Text, nullable=True),
        sa.Column("batch_size", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("rate_limit_per_second", sa.Integer, nullable=False, server_default="100"),
        sa.Column("max_concurrency", sa.Integer, nullable=False, server_default="4"),
        sa.Column("estimated_row_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("processed_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pause_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("requester_id", sa.String(96), nullable=False),
        sa.Column("authorization_ticket", sa.String(96), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_backfill_id_not_empty"),
        sa.CheckConstraint("state IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')", name="ck_backfill_state_valid"),
        sa.CheckConstraint("batch_size > 0", name="ck_backfill_batch_size_positive"),
        sa.Index("ix_backfill_state", "state"),
        sa.Index("ix_backfill_table", "target_table"),
    )

    # Backfill batches table - individual batch tracking
    op.create_table(
        "backfill_batches",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("job_id", sa.String(96), sa.ForeignKey("backfill_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offset", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("limit", sa.Integer, nullable=False),
        sa.Column("lease_token", sa.String(128), nullable=False),
        sa.Column("checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_batch_id_not_empty"),
        sa.Index("ix_batch_job", "job_id"),
    )

    # Retention policies table
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False, unique=True),
        sa.Column("retention_days", sa.Integer, nullable=True),
        sa.Column("policy", sa.String(32), nullable=False, server_default="after_certification"),
        sa.Column("legal_hold", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tombstone_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_retention_id_not_empty"),
        sa.CheckConstraint("policy IN ('after_certification', 'after_release', 'legal_hold', 'indefinite')", name="ck_retention_policy_valid"),
    )

    # Tombstones table - immutable deletion markers
    op.create_table(
        "tombstones",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("original_id", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("deletion_action", sa.String(32), nullable=False),
        sa.Column("deletion_reason", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("project_id", sa.String(160), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("deletion_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_tombstone_id_not_empty"),
        sa.CheckConstraint("deletion_action IN ('soft_delete', 'crypto_erase', 'tombstone')", name="ck_tombstone_action_valid"),
        sa.Index("ix_tombstone_original", "original_id"),
        sa.Index("ix_tombstone_entity_type", "entity_type"),
        sa.Index("ix_tombstone_deletion_hash", "deletion_hash"),
    )

    # Rollback plans table
    op.create_table(
        "rollback_plans",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("target_version", sa.String(32), nullable=False),
        sa.Column("from_version", sa.String(32), nullable=False),
        sa.Column("rollback_reason", sa.Text, nullable=False),
        sa.Column("preserve_new_evidence", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(96), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_rollback_id_not_empty"),
        sa.Index("ix_rollback_target", "target_version"),
        sa.Index("ix_rollback_from", "from_version"),
    )

    # Add RLS for lifecycle tables
    op.execute("ALTER TABLE regrade_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE backfill_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE backfill_batches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE retention_policies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tombstones ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rollback_plans ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY regrade_jobs_project_isolation ON regrade_jobs
        USING (run_id IN (SELECT run_id FROM experiments WHERE project_id = current_setting('we3.project_id', true)))
        WITH CHECK (run_id IN (SELECT run_id FROM experiments WHERE project_id = current_setting('we3.project_id', true)))
    """)

    op.execute("""
        CREATE POLICY backfill_jobs_project_isolation ON backfill_jobs
        USING (true)  -- Admin access with application-level controls
        WITH CHECK (true)
    """)

    op.execute("""
        CREATE POLICY backfill_batches_project_isolation ON backfill_batches
        USING (job_id IN (SELECT id FROM backfill_jobs))
        WITH CHECK (job_id IN (SELECT id FROM backfill_jobs))
    """)

    op.execute("""
        CREATE POLICY retention_policies_admin_only ON retention_policies
        USING (true)  -- Admin access only
        WITH CHECK (true)
    """)

    op.execute("""
        CREATE POLICY tombstones_project_isolation ON tombstones
        USING (project_id = current_setting('we3.project_id', true))
        WITH CHECK (project_id = current_setting('we3.project_id', true))
    """)

    op.execute("""
        CREATE POLICY rollback_plans_admin_only ON rollback_plans
        USING (true)  -- Admin access only
        WITH CHECK (true)
    """)


def downgrade() -> None:
    """Drop lifecycle workflow tables."""
    op.execute("DROP POLICY IF EXISTS rollback_plans_admin_only ON rollback_plans")
    op.execute("DROP POLICY IF EXISTS tombstones_project_isolation ON tombstones")
    op.execute("DROP POLICY IF EXISTS retention_policies_admin_only ON retention_policies")
    op.execute("DROP POLICY IF EXISTS backfill_batches_project_isolation ON backfill_batches")
    op.execute("DROP POLICY IF EXISTS backfill_jobs_project_isolation ON backfill_jobs")
    op.execute("DROP POLICY IF EXISTS regrade_jobs_project_isolation ON regrade_jobs")

    op.drop_table("rollback_plans")
    op.drop_table("tombstones")
    op.drop_table("retention_policies")
    op.drop_table("backfill_batches")
    op.drop_table("backfill_jobs")
    op.drop_table("regrade_jobs")