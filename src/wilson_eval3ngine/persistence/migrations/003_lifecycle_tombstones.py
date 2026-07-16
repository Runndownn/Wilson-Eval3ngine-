"""Lifecycle, regrade, backfill, retention, and deletion migrations.

T3.1.5 - Migration for immutable grade versions, tombstones, and lifecycle job tracking.
"""
from __future__ import annotations

from . import op
import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Boolean,
    JSON,
)


revision = "003_lifecycle_tombstones"
down_revision = "002_outbox_and_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create lifecycle tables with RLS policies."""
    op.create_table(
        "grade_versions",
        sa.Column("id", String(96), primary_key=True),
        sa.Column("project_id", String(160), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("run_id", String(96), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_label", String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("grader_version", String(128), nullable=False),
        sa.Column("evidence_hash", String(64), nullable=False),
        sa.Column("superseded_by_id", String(96)),
        sa.Column("previous_hash", String(64)),  # Audit chain linkage
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        Index("ix_grade_versions_project_run", "project_id", "run_id"),
        Index("ix_grade_versions_superseded", "superseded_by_id"),
    )

    op.create_table(
        "deletion_tombstones",
        sa.Column("id", String(96), primary_key=True),
        sa.Column("original_id", String(96), nullable=False),
        sa.Column("project_id", String(160), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("table_name", String(64), nullable=False),
        sa.Column("deleted_at", DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_by", String(255), nullable=False),
        sa.Column("deletion_reason", String(255), nullable=False),
        sa.Column("original_hash", String(64), nullable=False),
        sa.Column("tombstone_hash", String(64), nullable=False),
        Index("ix_tombstones_project_original", "project_id", "original_id"),
        Index("ix_tombstones_table", "table_name"),
    )

    op.create_table(
        "retention_policies",
        sa.Column("id", String(96), primary_key=True),
        sa.Column("project_id", String(160), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("classification", String(32), nullable=False),  # Public, Internal, Confidential, Restricted, Secret
        sa.Column("retention_days", Integer, nullable=False),
        sa.Column("hold_state", String(32), nullable=False, server_default="none"),
        sa.Column("legal_hold_reason", String(255)),
        sa.Column("policy_version", String(32), nullable=False),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        Index("ix_retention_project_class", "project_id", "classification"),
    )

    op.create_table(
        "lifecycle_jobs",
        sa.Column("id", String(96), primary_key=True),
        sa.Column("project_id", String(160), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation_type", String(64), nullable=False),
        sa.Column("target_ids", JSON, nullable=False),
        sa.Column("dry_run", Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("batch_size", Integer, nullable=False, server_default="1000"),
        sa.Column("processed_count", Integer, nullable=False, server_default="0"),
        sa.Column("total_target_count", Integer, nullable=False),
        sa.Column("checkpoint_token", String(64)),
        sa.Column("hold_state", String(32), nullable=False, server_default="none"),
        sa.Column("policy_version", String(32), nullable=False),
        sa.Column("started_at", DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", DateTime(timezone=True)),
        sa.Column("failed_at", DateTime(timezone=True)),
        sa.Column("error_message", String(1024)),
        Index("ix_lifecycle_jobs_project_state", "project_id", "operation_type"),
        Index("ix_lifecycle_jobs_checkpoint", "checkpoint_token"),
    )

    # RLS policies for lifecycle tables
    op.execute("""
        CREATE POLICY grade_versions_rls ON grade_versions
        FOR ALL TO application_role
        USING (project_id = current_setting('app.project_id')::text)
        WITH CHECK (project_id = current_setting('app.project_id')::text)
    """)

    op.execute("""
        CREATE POLICY tombstones_rls ON deletion_tombstones
        FOR ALL TO application_role
        USING (project_id = current_setting('app.project_id')::text)
        WITH CHECK (project_id = current_setting('app.project_id')::text)
    """)

    op.execute("""
        CREATE POLICY retention_rls ON retention_policies
        FOR ALL TO application_role
        USING (project_id = current_setting('app.project_id')::text)
        WITH CHECK (project_id = current_setting('app.project_id')::text)
    """)

    op.execute("""
        CREATE POLICY lifecycle_jobs_rls ON lifecycle_jobs
        FOR ALL TO application_role
        USING (project_id = current_setting('app.project_id')::text)
        WITH CHECK (project_id = current_setting('app.project_id')::text)
    """)


def downgrade() -> None:
    """Remove lifecycle tables and policies."""
    op.execute("DROP POLICY IF EXISTS grade_versions_rls ON grade_versions")
    op.execute("DROP POLICY IF EXISTS tombstones_rls ON deletion_tombstones")
    op.execute("DROP POLICY IF EXISTS retention_rls ON retention_policies")
    op.execute("DROP POLICY IF EXISTS lifecycle_jobs_rls ON lifecycle_jobs")

    op.drop_table("lifecycle_jobs")
    op.drop_table("retention_policies")
    op.drop_table("deletion_tombstones")
    op.drop_table("grade_versions")