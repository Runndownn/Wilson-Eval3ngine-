"""Scheduler state machine and fenced lease fields for jobs table.

Revision ID: 004_scheduler_lease_fields
Revises: 003_lifecycle_tombstones
Create Date: 2026-07-15

Prerequisites: 003_lifecycle_tombstones
Lock Risk: MEDIUM - ALTER TABLE with column additions
Compatible Application Versions: >=0.4.0

Adds:
- lease_version: Integer for optimistic concurrency control
- lease_token: String for lease ownership verification
- error_message: Extended error details field
- Updated job state constraint for full lifecycle states
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "004_scheduler_lease_fields"
down_revision = "003_lifecycle_tombstones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add scheduler lease fields to jobs table."""
    # Add lease_version column for optimistic concurrency
    op.add_column(
        "jobs",
        sa.Column("lease_version", sa.Integer(), nullable=True),
    )

    # Add lease_token for ownership verification
    op.add_column(
        "jobs",
        sa.Column("lease_token", sa.String(128), nullable=True),
    )

    # Extend error_message for detailed error tracking
    op.add_column(
        "jobs",
        sa.Column("error_message", sa.String(1024), nullable=True),
    )

    # Add index for efficient stale lease queries
    op.create_index(
        "ix_jobs_lease_expiry",
        "jobs",
        ["leased_until"],
        postgresql_where=text("state = 'leased'"),
    )

    # Update state constraint to include all scheduler states
    op.alter_column(
        "jobs",
        "state",
        existing_type=sa.String(32),
        nullable=False,
        server_default="pending",
    )


def downgrade() -> None:
    """Remove scheduler lease fields."""
    op.drop_index("ix_jobs_lease_expiry", table_name="jobs")
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "lease_token")
    op.drop_column("jobs", "lease_version")