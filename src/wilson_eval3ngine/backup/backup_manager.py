"""Backup and recovery controls.

The repository has a substantial recovery model and reconciliation surface, but
native encrypted PostgreSQL backup creation, WAL archival, and isolated restore
execution are not yet complete.  Those operations fail closed here rather than
returning metadata that could be mistaken for production protection.

Externally managed backups can be registered with durable local metadata so the
planning/integrity portions of the module remain useful while deployment-grade
backup execution is supplied by the approved database/object-storage platform.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.pool import NullPool

from ..security.signing import KeyPurpose, KeyRecord, TrustRegistry
from ..util import sha256_hex, utc_now

logger = logging.getLogger(__name__)


class BackupCapabilityError(RuntimeError):
    """Raised when a recovery operation is intentionally not production-ready."""


class BackupType(str, Enum):
    FULL = "full"
    WAL = "wal"
    INCREMENTAL = "incremental"


class BackupStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BackupMetadata:
    backup_id: str
    backup_type: BackupType
    backup_timestamp: datetime
    database_name: str
    database_size_bytes: int
    wal_start_lsn: str
    wal_end_lsn: str
    backup_duration_seconds: float
    encrypted: bool
    key_id: str
    checksum_sha256: str
    signature_sha256: str | None = None
    storage_location: str = ""
    status: BackupStatus = BackupStatus.COMPLETED
    verification_timestamp: datetime | None = None
    retention_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "backup_timestamp": self.backup_timestamp.isoformat(),
            "database_name": self.database_name,
            "database_size_bytes": self.database_size_bytes,
            "wal_start_lsn": self.wal_start_lsn,
            "wal_end_lsn": self.wal_end_lsn,
            "backup_duration_seconds": self.backup_duration_seconds,
            "encrypted": self.encrypted,
            "key_id": self.key_id,
            "checksum_sha256": self.checksum_sha256,
            "signature_sha256": self.signature_sha256,
            "storage_location": self.storage_location,
            "status": self.status.value,
            "verification_timestamp": (
                self.verification_timestamp.isoformat()
                if self.verification_timestamp
                else None
            ),
            "retention_days": self.retention_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupMetadata":
        return cls(
            backup_id=str(data["backup_id"]),
            backup_type=BackupType(str(data["backup_type"])),
            backup_timestamp=datetime.fromisoformat(str(data["backup_timestamp"])),
            database_name=str(data.get("database_name", "")),
            database_size_bytes=int(data.get("database_size_bytes", 0)),
            wal_start_lsn=str(data.get("wal_start_lsn", "")),
            wal_end_lsn=str(data.get("wal_end_lsn", "")),
            backup_duration_seconds=float(data.get("backup_duration_seconds", 0.0)),
            encrypted=bool(data.get("encrypted", False)),
            key_id=str(data.get("key_id", "")),
            checksum_sha256=str(data.get("checksum_sha256", "")),
            signature_sha256=(
                str(data["signature_sha256"])
                if data.get("signature_sha256")
                else None
            ),
            storage_location=str(data.get("storage_location", "")),
            status=BackupStatus(str(data.get("status", BackupStatus.COMPLETED.value))),
            verification_timestamp=(
                datetime.fromisoformat(str(data["verification_timestamp"]))
                if data.get("verification_timestamp")
                else None
            ),
            retention_days=int(data.get("retention_days", 30)),
        )


@dataclass
class RestorePlan:
    plan_id: str
    target_timestamp: datetime
    backup_sequence: list[str]
    wal_segments_needed: list[str]
    estimated_restore_time_minutes: int
    isolated_environment: str
    created_at: datetime = field(default_factory=utc_now)
    approved_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "target_timestamp": self.target_timestamp.isoformat(),
            "backup_sequence": self.backup_sequence,
            "wal_segments_needed": self.wal_segments_needed,
            "estimated_restore_time_minutes": self.estimated_restore_time_minutes,
            "isolated_environment": self.isolated_environment,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
        }


@dataclass
class ReconciliationReport:
    report_id: str
    restored_timestamp: datetime
    verified_timestamp: datetime
    total_runs: int
    runs_matched: int
    runs_missing: int
    total_classifications: int
    classifications_matched: int
    audit_chain_valid: bool
    outbox_events_pending: int
    metric_snapshots_matched: int
    gate_decisions_matched: int
    provenance_edges_matched: int
    discrepancies: list[str] = field(default_factory=list)
    reconciliation_signature: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        status = (
            "pass"
            if self.runs_missing == 0
            and self.audit_chain_valid
            and self.outbox_events_pending == 0
            and not self.discrepancies
            else "fail"
        )
        return {
            "report_id": self.report_id,
            "restored_timestamp": self.restored_timestamp.isoformat(),
            "verified_timestamp": self.verified_timestamp.isoformat(),
            "status": status,
            "totals": {
                "runs": self.total_runs,
                "classifications": self.total_classifications,
                "audit_chain_valid": self.audit_chain_valid,
                "outbox_events_pending": self.outbox_events_pending,
            },
            "matched": {
                "runs": self.runs_matched,
                "classifications": self.classifications_matched,
                "metric_snapshots": self.metric_snapshots_matched,
                "gate_decisions": self.gate_decisions_matched,
                "provenance_edges": self.provenance_edges_matched,
            },
            "missing": {"runs": self.runs_missing},
            "discrepancies": self.discrepancies,
            "signature": self.reconciliation_signature,
        }


class ObjectStoreBackup(Protocol):
    def upload_backup(self, local_path: Path, backup_id: str) -> str: ...
    def download_backup(self, backup_id: str, destination: Path) -> Path: ...
    def verify_backup(self, backup_id: str) -> bool: ...


class PostgreSQLBackupAdapter(Protocol):
    def create_base_backup(self, destination: Path) -> bool: ...
    def archive_wal(self, destination: Path) -> bool: ...
    def restore_backup(self, source: Path, target_database_url: str) -> bool: ...


def _directory_content_sha256(root: Path) -> str:
    """Hash relative names and file bytes for a deterministic directory digest."""
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    return digest.hexdigest()


class BackupManager:
    """Recovery metadata/planning manager.

    Native encrypted backup and WAL creation intentionally fail closed until a
    real encryption/object-storage/WAL implementation is wired.  The manager
    can register externally produced backups and persists their metadata under
    ``backup_root`` so separate processes see the same catalogue.
    """

    RPO_MINUTES = 15
    RTO_HOURS = 4
    RETENTION_DAYS = 30
    CATALOG_NAME = "backup_catalog.v1.json"

    def __init__(
        self,
        database_url: str,
        backup_root: Path | str,
        object_store: ObjectStoreBackup | None = None,
        trust_registry: TrustRegistry | None = None,
    ) -> None:
        self.database_url = database_url
        self.backup_root = Path(backup_root)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.object_store = object_store
        self.trust_registry = trust_registry
        self._catalog_path = self.backup_root / self.CATALOG_NAME
        self._backups: dict[str, BackupMetadata] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not self._catalog_path.exists():
            return
        try:
            raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
            for item in raw.get("backups", []):
                metadata = BackupMetadata.from_dict(item)
                self._backups[metadata.backup_id] = metadata
        except Exception as exc:
            raise BackupCapabilityError(
                f"Backup catalogue is unreadable: {self._catalog_path}: {exc}"
            ) from exc

    def _save_catalog(self) -> None:
        payload = {
            "schema_version": "we3.backup_catalog.v1",
            "updated_at": utc_now().isoformat(),
            "backups": [
                backup.to_dict()
                for backup in sorted(
                    self._backups.values(), key=lambda item: item.backup_timestamp
                )
            ],
        }
        temporary = self._catalog_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._catalog_path)

    def register_external_backup(
        self,
        metadata: BackupMetadata,
        *,
        local_backup_path: Path | str | None = None,
    ) -> BackupMetadata:
        """Register backup metadata produced by an approved external system.

        If a local path is supplied, its content digest must match the metadata
        before the record is accepted.  Encryption truth still belongs to the
        external system's evidence; WE3 does not infer it from ``key_id``.
        """
        if not metadata.checksum_sha256:
            raise ValueError("External backup metadata requires a content checksum")
        if metadata.encrypted and not metadata.key_id:
            raise ValueError("Encrypted backup metadata requires a key identifier")
        if local_backup_path is not None:
            actual = _directory_content_sha256(Path(local_backup_path))
            if actual != metadata.checksum_sha256:
                raise ValueError("External backup content checksum does not match metadata")
        self._backups[metadata.backup_id] = metadata
        self._save_catalog()
        return metadata

    def create_full_backup(self, encryption_key_id: str) -> BackupMetadata:
        """Fail closed until native encrypted base-backup creation is complete."""
        del encryption_key_id
        raise BackupCapabilityError(
            "Native encrypted PostgreSQL backup creation is not yet implemented. "
            "Use the approved platform backup/encryption service and register its "
            "verified metadata with register_external_backup()."
        )

    def create_wal_archive(self, encryption_key_id: str) -> BackupMetadata:
        """Fail closed until native WAL archival is implemented."""
        del encryption_key_id
        raise BackupCapabilityError(
            "Native WAL archival is not yet implemented. Use the approved "
            "PostgreSQL/platform WAL archive and register verified WAL metadata."
        )

    def generate_restore_plan(self, target_timestamp: datetime) -> RestorePlan:
        """Build a plan from a real recorded base backup and WAL catalogue.

        No WAL segment names are synthesized.  If the target is later than the
        selected full backup, at least one registered WAL record must cover the
        target and the final WAL record must declare an end LSN.
        """
        full_backups = sorted(
            (
                backup
                for backup in self._backups.values()
                if backup.backup_type == BackupType.FULL
                and backup.status in {BackupStatus.COMPLETED, BackupStatus.VERIFIED}
                and backup.backup_timestamp <= target_timestamp
            ),
            key=lambda item: item.backup_timestamp,
        )
        if not full_backups:
            raise ValueError("No suitable backup found for target timestamp")

        base = full_backups[-1]
        wal_backups = sorted(
            (
                backup
                for backup in self._backups.values()
                if backup.backup_type == BackupType.WAL
                and backup.status in {BackupStatus.COMPLETED, BackupStatus.VERIFIED}
                and base.backup_timestamp < backup.backup_timestamp <= target_timestamp
            ),
            key=lambda item: item.backup_timestamp,
        )

        if target_timestamp > base.backup_timestamp:
            if not wal_backups:
                raise ValueError(
                    "No verified WAL coverage is recorded after the selected full backup"
                )
            if not wal_backups[-1].wal_end_lsn:
                raise ValueError("Final WAL record does not declare an end LSN")

        sequence = [base.backup_id] + [item.backup_id for item in wal_backups]
        wal_ids = [item.backup_id for item in wal_backups]
        seed = sha256_hex(
            f"{target_timestamp.isoformat()}:{','.join(sequence)}".encode("utf-8")
        )
        return RestorePlan(
            plan_id=f"restore_{seed[:16]}",
            target_timestamp=target_timestamp,
            backup_sequence=sequence,
            wal_segments_needed=wal_ids,
            estimated_restore_time_minutes=max(30, 30 + 10 * len(wal_ids)),
            isolated_environment=f"restore-{seed[:12]}",
        )

    def verify_backup_integrity(
        self,
        backup_id: str,
        signing_key_path: Path | None = None,
    ) -> bool:
        """Verify local backup content digest; fail closed for unimplemented signatures."""
        metadata = self._backups.get(backup_id)
        if metadata is None:
            return False
        backup_dir = self.backup_root / backup_id
        if not backup_dir.is_dir():
            return False
        try:
            actual = _directory_content_sha256(backup_dir)
        except OSError:
            return False
        if actual != metadata.checksum_sha256:
            return False

        if metadata.signature_sha256 or signing_key_path or self.trust_registry:
            logger.warning(
                "Backup %s requested signature/trust verification, but the native "
                "signed backup-manifest verifier is not yet implemented",
                backup_id,
            )
            return False

        if metadata.encrypted:
            logger.warning(
                "Backup %s is marked encrypted, but this manager cannot independently "
                "verify external encryption/KMS evidence",
                backup_id,
            )

        metadata.verification_timestamp = utc_now()
        metadata.status = BackupStatus.VERIFIED
        self._save_catalog()
        return True

    def list_backups(self, limit: int | None = None) -> list[BackupMetadata]:
        backups = sorted(
            self._backups.values(), key=lambda item: item.backup_timestamp, reverse=True
        )
        return backups[:limit] if limit is not None else backups


class RecoveryOrchestrator:
    """Coordinates restore planning and structural reconciliation.

    Actual isolated restore execution fails closed until the database restore/WAL
    replay implementation is wired and evidenced.
    """

    def __init__(self, backup_manager: BackupManager, database_url: str) -> None:
        self.backup_manager = backup_manager
        self.database_url = database_url

    def execute_isolated_restore(
        self,
        plan: RestorePlan,
        isolated_database_url: str,
    ) -> bool:
        del plan, isolated_database_url
        raise BackupCapabilityError(
            "Isolated PostgreSQL restore/PITR execution is not yet implemented. "
            "A restore must not be reported successful until database restore, WAL "
            "replay, and reconciliation actually execute."
        )

    def reconcile_restored_state(
        self,
        isolated_database_url: str,
        signing_key_path: Path | None = None,
    ) -> ReconciliationReport:
        """Perform structural restored-state reconciliation.

        Audit-chain validity deliberately fails closed when audit events exist;
        this method does not yet perform the repository's full cryptographic
        hash-chain verification.  That prevents a non-empty-hash check from
        masquerading as chain verification.
        """
        report_id = f"recon_{sha256_hex(utc_now().isoformat())[:16]}"
        engine = create_engine(isolated_database_url, poolclass=NullPool, future=True)
        discrepancies: list[str] = []

        try:
            with engine.connect() as conn:
                total_runs = conn.execute(sql_text("SELECT COUNT(*) FROM runs")).scalar() or 0
                runs_matched = conn.execute(
                    sql_text("SELECT COUNT(*) FROM runs WHERE state = 'completed'")
                ).scalar() or 0
                runs_missing = total_runs - runs_matched

                total_classifications = conn.execute(
                    sql_text("SELECT COUNT(*) FROM classifications")
                ).scalar() or 0
                classifications_matched = conn.execute(
                    sql_text(
                        "SELECT COUNT(*) FROM classifications "
                        "WHERE superseded_by_id IS NULL"
                    )
                ).scalar() or 0

                audit_count = conn.execute(
                    sql_text("SELECT COUNT(*) FROM audit_events")
                ).scalar() or 0
                audit_chain_valid = audit_count == 0
                if audit_count:
                    discrepancies.append(
                        "Cryptographic audit-chain verification is not yet wired into recovery reconciliation"
                    )

                if engine.dialect.name == "postgresql":
                    outbox_sql = sql_text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE COALESCE(payload_json ->> 'processed', 'false') <> 'true'"
                    )
                    lineage_sql = sql_text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE payload_json -> 'lineage' IS NOT NULL"
                    )
                else:
                    outbox_sql = sql_text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE json_extract(payload_json, '$.processed') IS NULL "
                        "OR json_extract(payload_json, '$.processed') = 'false' "
                        "OR json_extract(payload_json, '$.processed') = 0"
                    )
                    lineage_sql = sql_text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE json_extract(payload_json, '$.lineage') IS NOT NULL"
                    )

                outbox_events_pending = conn.execute(outbox_sql).scalar() or 0
                metric_snapshots_matched = conn.execute(
                    sql_text("SELECT COUNT(*) FROM metric_snapshots")
                ).scalar() or 0
                gate_decisions_matched = conn.execute(
                    sql_text("SELECT COUNT(*) FROM gate_decisions")
                ).scalar() or 0
                provenance_edges_matched = conn.execute(lineage_sql).scalar() or 0
        finally:
            engine.dispose()

        report = ReconciliationReport(
            report_id=report_id,
            restored_timestamp=utc_now(),
            verified_timestamp=utc_now(),
            total_runs=total_runs,
            runs_matched=runs_matched,
            runs_missing=runs_missing,
            total_classifications=total_classifications,
            classifications_matched=classifications_matched,
            audit_chain_valid=audit_chain_valid,
            outbox_events_pending=outbox_events_pending,
            metric_snapshots_matched=metric_snapshots_matched,
            gate_decisions_matched=gate_decisions_matched,
            provenance_edges_matched=provenance_edges_matched,
            discrepancies=discrepancies,
        )

        if signing_key_path:
            from ..security.signing import load_private_key, sign_bytes

            private_key = load_private_key(signing_key_path)
            payload = json.dumps(report.to_dict(), sort_keys=True).encode("utf-8")
            report.reconciliation_signature = sign_bytes(payload, private_key)

        return report


class KeyBackupManager:
    """Preserves non-secret key/trust metadata for recovery planning."""

    def __init__(self, backup_root: Path) -> None:
        self.backup_root = Path(backup_root) / "keys"
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def export_key_metadata(
        self,
        key_record: KeyRecord,
        backup_key_purpose: KeyPurpose,
    ) -> dict[str, Any]:
        return {
            "key_id": key_record.key_id,
            "purpose": key_record.purpose.value,
            "owner": key_record.owner,
            "created_at": key_record.created_at,
            "active": key_record.active,
            "expires_at": key_record.expires_at,
            "parent_key_id": key_record.parent_key_id,
            "fips_validation": key_record.fips_validation,
            "backup_purpose": backup_key_purpose.value,
        }

    def preserve_trust_registry(
        self, trust_registry: TrustRegistry, backup_key_purpose: KeyPurpose
    ) -> dict[str, Any]:
        if not hasattr(trust_registry, "_trusted_fingerprints"):
            return {"trusted_fingerprints": [], "revoked_fingerprints": []}
        return {
            "trusted_fingerprints": list(trust_registry._trusted_fingerprints),
            "revoked_fingerprints": list(trust_registry._revoked_fingerprints),
            "backup_purpose": backup_key_purpose.value,
        }


def create_recovery_verification_manifest(
    backup_ids: list[str],
    restore_timestamp: datetime,
    reconciliation_report: ReconciliationReport,
    approvers: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "we3.recovery_manifest.v1",
        "generated_at": utc_now().isoformat(),
        "backup_sequence": backup_ids,
        "restore_timestamp": restore_timestamp.isoformat(),
        "reconciliation_status": reconciliation_report.to_dict()["status"],
        "approvals": {
            "required": 2,
            "received": len(approvers),
            "approvers": approvers,
        },
        "re_certification_required": reconciliation_report.runs_missing > 0
        or not reconciliation_report.audit_chain_valid
        or reconciliation_report.outbox_events_pending > 0
        or bool(reconciliation_report.discrepancies),
    }


__all__ = [
    "BackupCapabilityError",
    "BackupType",
    "BackupStatus",
    "BackupMetadata",
    "RestorePlan",
    "ReconciliationReport",
    "ObjectStoreBackup",
    "PostgreSQLBackupAdapter",
    "BackupManager",
    "RecoveryOrchestrator",
    "KeyBackupManager",
    "create_recovery_verification_manifest",
]
