"""Align backup/recovery persistence with encrypted PITR evidence.

Revision ID: 008_backup_evidence_v2
Revises: 007_rls_policies
Create Date: 2026-08-22

Migration 006 introduced the first recovery tables before the operational
backup implementation existed. It is retained as migration history. This
revision augments that schema with the identities that the v2 recovery code
actually uses: PostgreSQL system/timeline/WAL identity, ciphertext and manifest
hashes, signer identity, storage version, verification state, and tool
provenance.

The backup-root ``backup_catalog.v2.json`` remains the operational catalogue
used by ``BackupManager``. This table is suitable for mirroring catalogue
records into a managed PostgreSQL control plane; it must not be treated as a
replacement for the encrypted backup objects themselves.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "008_backup_evidence_v2"
down_revision = "007_rls_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backup_metadata",
        sa.Column("database_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("database_system_identifier", sa.String(64), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("timeline_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("wal_segment_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("wal_segment_name", sa.String(24), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("backup_duration_seconds", sa.Float(), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("ciphertext_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("manifest_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("signer_fingerprint_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("storage_location", sa.String(1024), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("storage_version", sa.String(255), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("verification_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "backup_metadata",
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        "backup_metadata",
        sa.Column(
            "tool_versions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_index(
        "ix_backup_database_identity",
        "backup_metadata",
        ["database_system_identifier", "timeline_id", "backup_timestamp"],
    )
    op.create_index(
        "ix_backup_wal_segment",
        "backup_metadata",
        ["database_system_identifier", "timeline_id", "wal_segment_name"],
    )
    op.create_check_constraint(
        "ck_backup_status_v2",
        "backup_metadata",
        "status IN ('pending', 'in_progress', 'completed', 'verified', 'failed', 'expired')",
    )
    op.create_check_constraint(
        "ck_backup_verified_requires_integrity_v2",
        "backup_metadata",
        "status <> 'verified' OR "
        "(encrypted = true AND ciphertext_sha256 IS NOT NULL "
        "AND manifest_sha256 IS NOT NULL AND signer_fingerprint_sha256 IS NOT NULL)",
    )

    op.add_column(
        "restore_plans",
        sa.Column("target_lsn", sa.String(64), nullable=True),
    )
    op.add_column(
        "restore_plans",
        sa.Column("database_system_identifier", sa.String(64), nullable=True),
    )
    op.add_column(
        "restore_plans",
        sa.Column("timeline_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "restore_plans",
        sa.Column("wal_segment_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "restore_plans",
        sa.Column("coverage_end_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "restore_plans",
        sa.Column("recovery_baseline_sha256", sa.String(64), nullable=True),
    )

    op.add_column(
        "reconciliation_reports",
        sa.Column("baseline_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "reconciliation_reports",
        sa.Column(
            "discrepancies",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("reconciliation_reports", "discrepancies")
    op.drop_column("reconciliation_reports", "baseline_sha256")

    op.drop_column("restore_plans", "recovery_baseline_sha256")
    op.drop_column("restore_plans", "coverage_end_timestamp")
    op.drop_column("restore_plans", "wal_segment_size_bytes")
    op.drop_column("restore_plans", "timeline_id")
    op.drop_column("restore_plans", "database_system_identifier")
    op.drop_column("restore_plans", "target_lsn")

    op.drop_constraint(
        "ck_backup_verified_requires_integrity_v2",
        "backup_metadata",
        type_="check",
    )
    op.drop_constraint("ck_backup_status_v2", "backup_metadata", type_="check")
    op.drop_index("ix_backup_wal_segment", table_name="backup_metadata")
    op.drop_index("ix_backup_database_identity", table_name="backup_metadata")

    op.drop_column("backup_metadata", "tool_versions")
    op.drop_column("backup_metadata", "retention_days")
    op.drop_column("backup_metadata", "verification_timestamp")
    op.drop_column("backup_metadata", "status")
    op.drop_column("backup_metadata", "storage_version")
    op.drop_column("backup_metadata", "storage_location")
    op.drop_column("backup_metadata", "signer_fingerprint_sha256")
    op.drop_column("backup_metadata", "manifest_sha256")
    op.drop_column("backup_metadata", "ciphertext_sha256")
    op.drop_column("backup_metadata", "backup_duration_seconds")
    op.drop_column("backup_metadata", "wal_segment_name")
    op.drop_column("backup_metadata", "wal_segment_size_bytes")
    op.drop_column("backup_metadata", "timeline_id")
    op.drop_column("backup_metadata", "database_system_identifier")
    op.drop_column("backup_metadata", "database_name")
