"""Encrypted PostgreSQL backup, WAL archival, PITR, and recovery evidence.

The package exposes the operational recovery primitives implemented by the
repository: streaming AES-256-GCM physical backups with KMS-wrapped data keys,
signed manifests, a durable local catalogue, real WAL-segment archival and gap
checking, isolated PostgreSQL restore/PITR, and reconciliation against a signed
pre-failure baseline. These source capabilities make recovery exercises
possible; they do not by themselves prove a deployment's RPO, RTO, key custody,
archive durability, or disaster-recovery readiness. Those claims require
executed evidence from the target environment.
"""

from .backup_manager import (
    BackupCapabilityError,
    BackupManager,
    BackupMetadata,
    BackupStatus,
    BackupType,
    KeyBackupManager,
    ReconciliationReport,
    RecoveryBaseline,
    RecoveryOrchestrator,
    RestoreExecutionResult,
    RestorePlan,
    capture_recovery_baseline,
    create_recovery_verification_manifest,
    verify_recovery_baseline,
)
from .kms import AWSKMSClient, build_backup_kms_from_env


__all__ = [
    "AWSKMSClient",
    "BackupCapabilityError",
    "BackupManager",
    "BackupMetadata",
    "BackupStatus",
    "BackupType",
    "KeyBackupManager",
    "ReconciliationReport",
    "RecoveryBaseline",
    "RecoveryOrchestrator",
    "RestoreExecutionResult",
    "RestorePlan",
    "build_backup_kms_from_env",
    "capture_recovery_baseline",
    "create_recovery_verification_manifest",
    "verify_recovery_baseline",
]
