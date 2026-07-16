"""Review and governance tables for human review workflow and release control.

Revision ID: 005_review_governance_schema
Revises: 004_scheduler_lease_fields
Create Date: 2026-07-16

Prerequisites: 004_scheduler_lease_fields
Lock Risk: MEDIUM - table creation with foreign key constraints
Compatible Application Versions: >=0.5.0

Adds:
- reviewers table: Qualified reviewer identity and status
- qualifications table: Reviewer qualifications with validity periods
- review_tasks table: Human review work items
- review_assignments table: Task-to-reviewer assignment records
- review_submissions table: Immutable review decision submissions
- adjudications table: Final dispute resolution records
- threshold_sets table: Versioned threshold configurations
- overrides table: Override requests with dual approval tracking
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005_review_governance_schema"
down_revision = "004_scheduler_lease_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create review and governance tables."""

    # Qualifications table - stores reviewer qualifications
    op.create_table(
        "qualifications",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("reviewer_id", sa.String(96), nullable=False, unique=True),
        sa.Column("languages", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("subject_expertise", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("safety_training_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("psychological_safety_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("max_daily_exposures", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_hourly_exposures", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_consecutive_reviews", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("certified_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("certification_evidence", sa.String(255)),
        sa.CheckConstraint("max_daily_exposures > 0", name="ck_qual_daily_exposures_pos"),
        sa.CheckConstraint("max_hourly_exposures > 0", name="ck_qual_hourly_exposures_pos"),
        sa.CheckConstraint("max_consecutive_reviews > 0", name="ck_qual_consecutive_pos"),
        sa.Index("ix_qualifications_reviewer_id", "reviewer_id"),
        sa.Index("ix_qualifications_expires_at", "expires_at"),
    )

    # Reviewers table - qualified human reviewers with workload tracking
    op.create_table(
        "reviewers",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("identity_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="inactive"),
        sa.Column("qualification_id", sa.String(96), sa.ForeignKey("qualifications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_adjudicator", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("current_active_reviews", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_exposures_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hourly_exposures_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_exposure_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'on_leave', 'expired')", name="ck_reviewers_status_valid"),
        sa.CheckConstraint("current_active_reviews >= 0", name="ck_reviewers_active_nonneg"),
        sa.CheckConstraint("daily_exposures_count >= 0", name="ck_reviewers_daily_nonneg"),
        sa.Index("ix_reviewers_project_id", "project_id"),
        sa.Index("ix_reviewers_identity_id", "identity_id"),
        sa.Index("ix_reviewers_status", "status"),
        sa.Index("ix_reviewers_adjudicator", "is_adjudicator"),
    )

    # Review Tasks table - human review work items
    op.create_table(
        "review_tasks",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(96), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_version_id", sa.String(255), nullable=False),
        sa.Column("prompt_family_id", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("assigned_reviewer_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("first_assigned_at", sa.DateTime(timezone=True)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("submission_json", postgresql.JSONB()),
        sa.Column("superseded_by_task_id", sa.String(96)),
        sa.Column("superseded_reason", sa.String(255)),
        sa.Column("state", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("state IN ('queued', 'assigned', 'in_review', 'submitted', 'adjudication_required', 'resolved', 'superseded', 'cancelled')", name="ck_review_tasks_state_valid"),
        sa.CheckConstraint("category IN ('critical_unsafe', 'ambiguity_resolution', 'low_confidence', 'disagreement', 'audit_sampling', 'adjudication')", name="ck_review_tasks_category_valid"),
        sa.Index("ix_review_tasks_project_id", "project_id"),
        sa.Index("ix_review_tasks_category", "category"),
        sa.Index("ix_review_tasks_due_at", "due_at"),
        sa.Index("ix_review_tasks_state", "state"),
        sa.Index("ix_review_tasks_run_id", "run_id"),
    )

    # Review Assignments table - immutable assignment records with recusal support
    op.create_table(
        "review_assignments",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(96), sa.ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigner", sa.String(255), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("recusal_at", sa.DateTime(timezone=True)),
        sa.Column("recusal_reason", sa.String(255)),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(reason) > 0", name="ck_assignments_reason_not_empty"),
        sa.Index("ix_assignments_task_id", "task_id"),
        sa.Index("ix_assignments_reviewer_id", "reviewer_id"),
        sa.Index("ix_assignments_recusal", "recusal_at"),
    )

    # Review Submissions table - immutable review decision records
    op.create_table(
        "review_submissions",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(96), sa.ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("primary_label", sa.String(64)),
        sa.Column("secondary_labels", postgresql.JSONB(), server_default="[]"),
        sa.Column("rationale", sa.Text),
        sa.Column("raw_revealed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reveal_reason", sa.String(255)),
        sa.Column("evidence_notes", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("decision IN ('approve_classification', 'override_classification', 'request_adjudication', 'abstain')", name="ck_submissions_decision_valid"),
        sa.Index("ix_submissions_task_id", "task_id"),
        sa.Index("ix_submissions_reviewer_id", "reviewer_id"),
    )

    # Adjudications table - final dispute resolution records
    op.create_table(
        "adjudications",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("task_id", sa.String(96), sa.ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adjudicator_id", sa.String(96), sa.ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("primary_label", sa.String(64)),
        sa.Column("secondary_labels", postgresql.JSONB(), server_default="[]"),
        sa.Column("rationale", sa.Text),
        sa.Column("reviewer_a_opinion", sa.String(64)),
        sa.Column("reviewer_b_opinion", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("decision IN ('approve_classification', 'override_classification', 'request_adjudication', 'abstain')", name="ck_adjud_decision_valid"),
        sa.Index("ix_adjudications_task_id", "task_id"),
        sa.Index("ix_adjudications_adjudicator_id", "adjudicator_id"),
    )

    # Threshold Sets table - versioned threshold configurations
    op.create_table(
        "threshold_sets",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("project_id", sa.String(160), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("threshold_set_id", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("calibration_evidence_sha256", sa.String(64), nullable=False),
        sa.Column("minimum_prompt_families", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("approved_by", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("minimum_prompt_families >= 1", name="ck_threshold_pf_min"),
        sa.CheckConstraint("length(rules_json) > 0", name="ck_threshold_rules_not_empty"),
        sa.Index("ix_threshold_sets_project_id", "project_id"),
        sa.Index("ix_threshold_sets_threshold_set_id", "threshold_set_id"),
        sa.UniqueConstraint("threshold_set_id", "version", name="uq_threshold_set_version"),
    )

    # Overrides table - override requests with dual approval tracking
    op.create_table(
        "overrides",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("gate_id", sa.String(96), nullable=False),
        sa.Column("requester", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("scope_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("approver_a", sa.String(255)),
        sa.Column("approver_b", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("compensating_controls", postgresql.JSONB(), server_default="[]"),
        sa.Column("follow_up_ticket", sa.String(255)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(rationale) > 0", name="ck_overrides_rationale_not_empty"),
        sa.Index("ix_overrides_gate_id", "gate_id"),
        sa.Index("ix_overrides_expires_at", "expires_at"),
        sa.Index("ix_overrides_approver_a", "approver_a"),
        sa.Index("ix_overrides_approver_b", "approver_b"),
    )


def downgrade() -> None:
    """Drop review and governance tables in reverse order."""
    op.drop_table("overrides")
    op.drop_table("threshold_sets")
    op.drop_table("adjudications")
    op.drop_table("review_submissions")
    op.drop_table("review_assignments")
    op.drop_table("review_tasks")
    op.drop_table("reviewers")
    op.drop_table("qualifications")