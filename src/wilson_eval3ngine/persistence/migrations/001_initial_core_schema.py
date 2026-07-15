"""Initial migration - creates all core tables.

Revision ID: 001_initial_core_schema
Revises:
Create Date: 2026-07-15

Prerequisites: None
Lock Risk: LOW - table creation only
Compatible Application Versions: >=0.1.0

This migration creates the core schema for experiments, runs, classifications,
metric snapshots, gate decisions, audit events, and jobs.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "001_initial_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all core tables."""
    # Projects table - foundation for multi-tenancy
    op.create_table(
        "projects",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_projects_id_not_empty"),
    )

    # Experiments table - tracks evaluation runs
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("lane", sa.String(64), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_experiments_id_not_empty"),
        sa.Index("ix_experiments_project_id", "project_id"),
    )

    # Runs table - individual model execution records
    op.create_table(
        "runs",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("experiment_id", sa.String(96), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logical_key", sa.String(64), nullable=False),
        sa.Column("case_version_id", sa.String(255), nullable=False),
        sa.Column("prompt_family_id", sa.String(255), nullable=False),
        sa.Column("model_config_id", sa.String(255), nullable=False),
        sa.Column("repetition_index", sa.Integer(), nullable=False),
        sa.Column("expected_treatment", sa.String(32), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("request_artifact_hash", sa.String(64)),
        sa.Column("response_artifact_hash", sa.String(64)),
        sa.Column("reliability_error", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_runs_id_not_empty"),
        sa.CheckConstraint("repetition_index >= 0", name="ck_runs_repetition_nonneg"),
    )
    op.create_unique_constraint("uq_run_logical", "runs", ["experiment_id", "logical_key"])
    op.create_index("ix_runs_project_experiment_state", "runs", ["project_id", "experiment_id", "state"])

    # Classifications table - grading results
    op.create_table(
        "classifications",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("run_id", sa.String(96), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_label", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("superseded_by_id", sa.String(96)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_classifications_confidence_range"),
        sa.Index("ix_classifications_project_id", "project_id"),
        sa.Index("ix_classifications_run_id", "run_id"),
    )

    # Metric Snapshots table
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("experiment_id", sa.String(96), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_config_id", sa.String(255), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_snapshots_id_not_empty"),
        sa.Index("ix_snapshots_project_id", "project_id"),
        sa.Index("ix_snapshots_experiment_id", "experiment_id"),
    )

    # Gate Decisions table
    op.create_table(
        "gate_decisions",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("experiment_id", sa.String(96), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_config_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_gates_id_not_empty"),
        sa.CheckConstraint("status IN ('pass', 'warning', 'block', 'indeterminate')", name="ck_gates_status_valid"),
        sa.Index("ix_gates_project_id", "project_id"),
        sa.Index("ix_gates_experiment_id", "experiment_id"),
    )

    # Audit Events table - immutable audit log
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_audit_id_not_empty"),
        sa.CheckConstraint("length(event_hash) = 64", name="ck_audit_hash_length"),
        sa.Index("ix_audit_project_id", "project_id"),
    )

    # Jobs table - background work queue
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("job_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("leased_until", sa.DateTime(timezone=True)),
        sa.Column("leased_by", sa.String(255)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(id) > 0", name="ck_jobs_id_not_empty"),
        sa.CheckConstraint("state IN ('pending', 'processing', 'succeeded', 'failed')", name="ck_jobs_state_valid"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count_nonneg"),
        sa.Index("ix_jobs_state_available", "state", "available_at"),
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("jobs")
    op.drop_table("audit_events")
    op.drop_table("gate_decisions")
    op.drop_table("metric_snapshots")
    op.drop_table("classifications")
    op.drop_table("runs")
    op.drop_table("experiments")
    op.drop_table("projects")