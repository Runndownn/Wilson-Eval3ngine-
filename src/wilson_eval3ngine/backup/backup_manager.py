"""Production-oriented encrypted PostgreSQL backup, PITR, and reconciliation.

The recovery path is deliberately evidence-driven. A backup becomes eligible
for restore only after its encrypted payload, canonical manifest, Ed25519
signature, KMS identity, PostgreSQL system identity, and durable catalogue entry
agree. PITR plans use actual archived WAL filenames and reject gaps. Restore
success means PostgreSQL actually starts from the restored physical backup,
replays the planned WAL to the requested target, and passes reconciliation
against a signed pre-failure baseline.

Runtime RPO/RTO claims still belong to the deployment that executes this code.
The module records measured recovery evidence; it does not turn configured
targets into observed facts.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine, inspect, text as sql_text
from sqlalchemy.pool import NullPool

from ..persistence.audit import verify_audit_records
from ..security.signing import (
    KeyPurpose,
    KeyRecord,
    SignatureEnvelope,
    TrustRegistry,
    load_private_key,
    sign_bytes,
    verify_bytes,
)
from ..storage.encrypted_store import KMSClient
from ..util import canonical_json, new_id, sha256_hex, utc_now
from .crypto import (
    EncryptionEnvelope,
    decrypt_file,
    encrypt_file,
    encrypt_stream,
    verify_ciphertext,
)
from .kms import kms_identity
from .postgres import (
    basebackup_command,
    capture_postgresql_identity,
    parse_postgresql_url,
    require_pg_tool,
    sqlalchemy_postgresql_url,
    tool_version,
    wal_segment_index,
    wal_segments_are_contiguous,
)


class BackupCapabilityError(RuntimeError):
    """Raised when backup/recovery prerequisites or trust checks are not met."""


class BackupType(StrEnum):
    FULL = "full"
    WAL = "wal"
    INCREMENTAL = "incremental"


class BackupStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BackupMetadata:
    """Durable catalogue record for one encrypted physical or WAL backup object."""

    backup_id: str
    backup_type: BackupType
    backup_timestamp: datetime
    database_name: str
    database_system_identifier: str
    timeline_id: int
    wal_segment_size_bytes: int
    wal_start_lsn: str
    wal_end_lsn: str
    wal_segment_name: str
    database_size_bytes: int
    backup_duration_seconds: float
    encrypted: bool
    key_id: str
    checksum_sha256: str
    ciphertext_sha256: str
    manifest_sha256: str
    signer_fingerprint_sha256: str
    storage_location: str
    storage_version: str
    status: BackupStatus = BackupStatus.COMPLETED
    verification_timestamp: datetime | None = None
    retention_days: int = 30
    tool_versions: dict[str, str] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        """Compatibility alias used by existing CLI/reporting code."""
        return self.database_size_bytes

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["backup_type"] = self.backup_type.value
        result["backup_timestamp"] = self.backup_timestamp.isoformat()
        result["status"] = self.status.value
        result["verification_timestamp"] = (
            self.verification_timestamp.isoformat()
            if self.verification_timestamp
            else None
        )
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupMetadata":
        return cls(
            backup_id=str(data["backup_id"]),
            backup_type=BackupType(str(data["backup_type"])),
            backup_timestamp=datetime.fromisoformat(str(data["backup_timestamp"])),
            database_name=str(data.get("database_name", "")),
            database_system_identifier=str(data.get("database_system_identifier", "")),
            timeline_id=int(data.get("timeline_id", 0)),
            wal_segment_size_bytes=int(data.get("wal_segment_size_bytes", 0)),
            wal_start_lsn=str(data.get("wal_start_lsn", "")),
            wal_end_lsn=str(data.get("wal_end_lsn", "")),
            wal_segment_name=str(data.get("wal_segment_name", "")),
            database_size_bytes=int(
                data.get("database_size_bytes", data.get("size_bytes", 0))
            ),
            backup_duration_seconds=float(data.get("backup_duration_seconds", 0.0)),
            encrypted=bool(data.get("encrypted", False)),
            key_id=str(data.get("key_id", "")),
            checksum_sha256=str(data.get("checksum_sha256", "")),
            ciphertext_sha256=str(data.get("ciphertext_sha256", "")),
            manifest_sha256=str(data.get("manifest_sha256", "")),
            signer_fingerprint_sha256=str(
                data.get("signer_fingerprint_sha256", "")
            ),
            storage_location=str(data.get("storage_location", "")),
            storage_version=str(data.get("storage_version", "")),
            status=BackupStatus(str(data.get("status", BackupStatus.COMPLETED.value))),
            verification_timestamp=(
                datetime.fromisoformat(str(data["verification_timestamp"]))
                if data.get("verification_timestamp")
                else None
            ),
            retention_days=int(data.get("retention_days", 30)),
            tool_versions=dict(data.get("tool_versions") or {}),
        )


@dataclass(frozen=True, slots=True)
class RecoveryBaseline:
    """Signed state summary used to judge whether a restore reconciled correctly."""

    captured_at: str
    total_runs: int
    total_classifications: int
    metric_snapshots: int
    gate_decisions: int
    provenance_edges: int
    outbox_pending: int
    audit_roots: dict[str, str]
    payload_sha256: str
    signature: dict[str, str] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": "we3.recovery_baseline.v1",
            "captured_at": self.captured_at,
            "total_runs": self.total_runs,
            "total_classifications": self.total_classifications,
            "metric_snapshots": self.metric_snapshots,
            "gate_decisions": self.gate_decisions,
            "provenance_edges": self.provenance_edges,
            "outbox_pending": self.outbox_pending,
            "audit_roots": dict(sorted(self.audit_roots.items())),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload(),
            "payload_sha256": self.payload_sha256,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RecoveryBaseline":
        return cls(
            captured_at=str(value["captured_at"]),
            total_runs=int(value["total_runs"]),
            total_classifications=int(value["total_classifications"]),
            metric_snapshots=int(value["metric_snapshots"]),
            gate_decisions=int(value["gate_decisions"]),
            provenance_edges=int(value["provenance_edges"]),
            outbox_pending=int(value["outbox_pending"]),
            audit_roots={str(k): str(v) for k, v in dict(value["audit_roots"]).items()},
            payload_sha256=str(value["payload_sha256"]),
            signature=(
                {str(k): str(v) for k, v in dict(value["signature"]).items()}
                if value.get("signature")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class RestorePlan:
    plan_id: str
    target_timestamp: datetime
    target_lsn: str | None
    backup_sequence: list[str]
    wal_segments_needed: list[str]
    estimated_restore_time_minutes: int
    isolated_environment: str
    database_system_identifier: str
    timeline_id: int
    wal_segment_size_bytes: int
    coverage_end_timestamp: datetime
    recovery_baseline_sha256: str
    created_at: datetime = field(default_factory=utc_now)
    approved_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "we3.restore_plan.v2",
            "plan_id": self.plan_id,
            "target_timestamp": self.target_timestamp.isoformat(),
            "target_lsn": self.target_lsn,
            "backup_sequence": list(self.backup_sequence),
            "wal_segments_needed": list(self.wal_segments_needed),
            "estimated_restore_time_minutes": self.estimated_restore_time_minutes,
            "isolated_environment": self.isolated_environment,
            "database_system_identifier": self.database_system_identifier,
            "timeline_id": self.timeline_id,
            "wal_segment_size_bytes": self.wal_segment_size_bytes,
            "coverage_end_timestamp": self.coverage_end_timestamp.isoformat(),
            "recovery_baseline_sha256": self.recovery_baseline_sha256,
            "created_at": self.created_at.isoformat(),
            "approved_by": list(self.approved_by),
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
    baseline_sha256: str = ""
    reconciliation_signature: SignatureEnvelope | None = None

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
            "baseline_sha256": self.baseline_sha256,
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
            "discrepancies": list(self.discrepancies),
            "signature": (
                self.reconciliation_signature.to_dict()
                if self.reconciliation_signature
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class RestoreExecutionResult:
    """Measured evidence from one isolated restore attempt."""

    success: bool
    plan_id: str
    started_at: str
    completed_at: str
    duration_seconds: float
    data_directory: str
    wal_archive_directory: str
    postgres_version: str
    pg_ctl_version: str
    log_sha256: str
    reconciliation: dict[str, Any]
    evidence_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _signature_from_dict(value: dict[str, Any]) -> SignatureEnvelope:
    return SignatureEnvelope(
        algorithm=str(value["algorithm"]),
        public_key_fingerprint_sha256=str(value["public_key_fingerprint_sha256"]),
        public_key_pem=str(value["public_key_pem"]),
        signature_base64=str(value["signature_base64"]),
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_physical_backup(archive: Path, destination: Path) -> None:
    """Extract a pg_basebackup tar while rejecting link/path traversal entries."""
    destination.mkdir(parents=True, exist_ok=False)
    destination.chmod(0o700)
    root = destination.resolve()
    with tarfile.open(archive, mode="r:") as bundle:
        members = bundle.getmembers()
        for member in members:
            if member.issym() or member.islnk() or member.isdev():
                raise BackupCapabilityError(
                    f"Physical backup contains unsupported link/device entry: {member.name}"
                )
            resolved = (root / member.name).resolve()
            if resolved != root and root not in resolved.parents:
                raise BackupCapabilityError(
                    f"Physical backup contains unsafe path: {member.name}"
                )
        bundle.extractall(root, members=members)


def _audit_rows_from_connection(conn) -> tuple[bool, dict[str, str]]:
    rows = conn.execute(
        sql_text(
            """
            SELECT id, project_id, event_type, aggregate_type, aggregate_id,
                   actor_id, payload_json, previous_hash, event_hash, created_at
            FROM audit_events
            ORDER BY project_id, created_at, id
            """
        )
    ).mappings().all()
    roots: dict[str, str] = {}
    valid = True
    by_project: dict[str, list[SimpleNamespace]] = {}
    for row in rows:
        payload = row["payload_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        item = SimpleNamespace(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            event_type=str(row["event_type"]),
            aggregate_type=str(row["aggregate_type"]),
            aggregate_id=str(row["aggregate_id"]),
            actor_id=str(row["actor_id"]),
            payload_json=dict(payload),
            previous_hash=(str(row["previous_hash"]) if row["previous_hash"] else None),
            event_hash=str(row["event_hash"]),
            created_at=row["created_at"],
        )
        by_project.setdefault(item.project_id, []).append(item)
    for project_id, project_rows in by_project.items():
        if not verify_audit_records(project_rows):
            valid = False
        elif project_rows:
            roots[project_id] = project_rows[-1].event_hash
    return valid, roots


def _table_count(conn, table_name: str) -> int:
    if table_name not in set(inspect(conn).get_table_names()):
        raise BackupCapabilityError(
            f"Recovery reconciliation requires table {table_name!r}, but it is absent"
        )
    return int(conn.execute(sql_text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one())


def capture_recovery_baseline(
    database_url: str,
    *,
    signing_key_path: Path,
) -> RecoveryBaseline:
    """Capture and sign the state expected after a target restore."""
    engine = create_engine(
        sqlalchemy_postgresql_url(database_url)
        if database_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))
        else database_url,
        poolclass=NullPool,
        future=True,
    )
    try:
        with engine.connect() as conn:
            audit_valid, audit_roots = _audit_rows_from_connection(conn)
            if not audit_valid:
                raise BackupCapabilityError(
                    "Cannot sign a recovery baseline while the audit chain is invalid"
                )
            payload = {
                "schema_version": "we3.recovery_baseline.v1",
                "captured_at": utc_now().isoformat(),
                "total_runs": _table_count(conn, "runs"),
                "total_classifications": _table_count(conn, "classifications"),
                "metric_snapshots": _table_count(conn, "metric_snapshots"),
                "gate_decisions": _table_count(conn, "gate_decisions"),
                "provenance_edges": _table_count(conn, "provenance_edges"),
                "outbox_pending": int(
                    conn.execute(
                        sql_text(
                            "SELECT COUNT(*) FROM outbox_events WHERE status <> 'delivered'"
                        )
                    ).scalar_one()
                ),
                "audit_roots": dict(sorted(audit_roots.items())),
            }
    finally:
        engine.dispose()

    digest = sha256_hex(canonical_json(payload))
    envelope = sign_bytes(canonical_json(payload), load_private_key(signing_key_path))
    return RecoveryBaseline(
        captured_at=str(payload["captured_at"]),
        total_runs=int(payload["total_runs"]),
        total_classifications=int(payload["total_classifications"]),
        metric_snapshots=int(payload["metric_snapshots"]),
        gate_decisions=int(payload["gate_decisions"]),
        provenance_edges=int(payload["provenance_edges"]),
        outbox_pending=int(payload["outbox_pending"]),
        audit_roots=dict(payload["audit_roots"]),
        payload_sha256=digest,
        signature=envelope.to_dict(),
    )


def verify_recovery_baseline(
    baseline: RecoveryBaseline,
    trust_registry: TrustRegistry,
) -> bool:
    payload = baseline.payload()
    if sha256_hex(canonical_json(payload)) != baseline.payload_sha256:
        return False
    if not baseline.signature:
        return False
    envelope = _signature_from_dict(baseline.signature)
    if not trust_registry.is_trusted(envelope.public_key_fingerprint_sha256):
        return False
    return verify_bytes(canonical_json(payload), envelope)


class BackupManager:
    """Creates encrypted, signed physical backups and a durable local catalogue."""

    RPO_MINUTES = 15
    RTO_HOURS = 4
    RETENTION_DAYS = 30
    CATALOG_NAME = "backup_catalog.v2.json"

    def __init__(
        self,
        database_url: str,
        backup_root: Path | str,
        *,
        kms_client: KMSClient | None = None,
        trust_registry: TrustRegistry | None = None,
    ) -> None:
        self.database_url = database_url
        self.backup_root = Path(backup_root)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.kms_client = kms_client
        self.trust_registry = trust_registry
        self._catalog_path = self.backup_root / self.CATALOG_NAME
        self._backups: dict[str, BackupMetadata] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not self._catalog_path.exists():
            return
        try:
            raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != "we3.backup_catalog.v2":
                raise BackupCapabilityError(
                    f"Unsupported backup catalogue schema: {raw.get('schema_version')!r}"
                )
            self._backups = {
                item["backup_id"]: BackupMetadata.from_dict(item)
                for item in raw.get("backups", [])
            }
        except BackupCapabilityError:
            raise
        except Exception as exc:
            raise BackupCapabilityError(
                f"Backup catalogue is unreadable: {self._catalog_path}: {exc}"
            ) from exc

    def _save_catalog(self) -> None:
        payload = {
            "schema_version": "we3.backup_catalog.v2",
            "updated_at": utc_now().isoformat(),
            "backups": [
                item.to_dict()
                for item in sorted(
                    self._backups.values(),
                    key=lambda value: (value.backup_timestamp, value.backup_id),
                )
            ],
        }
        temporary = self._catalog_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self._catalog_path)

    def _require_crypto(self) -> KMSClient:
        if self.kms_client is None:
            raise BackupCapabilityError(
                "Backup encryption requires a configured KMS client"
            )
        return self.kms_client

    def _write_manifest(
        self,
        backup_dir: Path,
        manifest: dict[str, Any],
        signing_key_path: Path,
    ) -> tuple[str, str]:
        manifest_bytes = canonical_json(manifest)
        manifest_sha = sha256_hex(manifest_bytes)
        envelope = sign_bytes(manifest_bytes, load_private_key(signing_key_path))
        manifest_path = backup_dir / "manifest.json"
        signature_path = backup_dir / "manifest.sig.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        signature_path.write_text(
            json.dumps(envelope.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return manifest_sha, envelope.public_key_fingerprint_sha256

    def _manifest_paths(self, metadata: BackupMetadata) -> tuple[Path, Path, Path]:
        backup_dir = self.backup_root / metadata.backup_id
        return (
            backup_dir / "manifest.json",
            backup_dir / "manifest.sig.json",
            self.backup_root / metadata.storage_location,
        )

    def _catalogue(self, metadata: BackupMetadata) -> BackupMetadata:
        self._backups[metadata.backup_id] = metadata
        self._save_catalog()
        return metadata

    def create_full_backup(
        self,
        encryption_key_id: str,
        signing_key_path: Path,
    ) -> BackupMetadata:
        """Stream pg_basebackup directly into AES-256-GCM encrypted storage."""
        kms = self._require_crypto()
        pre = capture_postgresql_identity(self.database_url)
        command, env = basebackup_command(self.database_url)
        backup_id = new_id("backup")
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(mode=0o700)
        ciphertext = backup_dir / "base.tar.we3enc"
        log_path = backup_dir / "pg_basebackup.log"
        started = time.monotonic()

        with log_path.open("wb") as log:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=log,
                env=env,
            )
            assert process.stdout is not None
            try:
                envelope = encrypt_stream(
                    process.stdout,
                    ciphertext,
                    kms_client=kms,
                    key_id=encryption_key_id,
                    kms_identity=kms_identity(kms, encryption_key_id),
                )
            except Exception:
                process.terminate()
                process.wait(timeout=30)
                shutil.rmtree(backup_dir, ignore_errors=True)
                raise
            return_code = process.wait()
        if return_code != 0:
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise BackupCapabilityError(
                f"pg_basebackup failed with exit status {return_code}"
            )

        post = capture_postgresql_identity(self.database_url)
        if (
            pre.system_identifier != post.system_identifier
            or pre.timeline_id != post.timeline_id
            or pre.wal_segment_size_bytes != post.wal_segment_size_bytes
        ):
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise BackupCapabilityError(
                "PostgreSQL system/timeline/WAL identity changed during base backup"
            )

        duration = time.monotonic() - started
        backup_timestamp = utc_now()
        storage_location = ciphertext.relative_to(self.backup_root).as_posix()
        manifest = {
            "schema_version": "we3.backup_manifest.v2",
            "backup_id": backup_id,
            "backup_type": BackupType.FULL.value,
            "created_at": backup_timestamp.isoformat(),
            "database": {
                "name": post.database_name,
                "system_identifier": post.system_identifier,
                "timeline_id": post.timeline_id,
                "wal_segment_size_bytes": post.wal_segment_size_bytes,
                "wal_start_lsn": pre.current_lsn,
                "wal_end_lsn": post.current_lsn,
                "wal_end_segment": post.current_wal_segment,
                "server_version": post.server_version,
            },
            "object": {
                "logical_name": "base.tar",
                "storage_location": storage_location,
                "storage_version": envelope.ciphertext_sha256,
                "encryption": envelope.to_dict(),
            },
            "tools": {
                "pg_basebackup": tool_version("pg_basebackup"),
            },
        }
        manifest_sha, fingerprint = self._write_manifest(
            backup_dir, manifest, signing_key_path
        )
        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            backup_timestamp=backup_timestamp,
            database_name=post.database_name,
            database_system_identifier=post.system_identifier,
            timeline_id=post.timeline_id,
            wal_segment_size_bytes=post.wal_segment_size_bytes,
            wal_start_lsn=pre.current_lsn,
            wal_end_lsn=post.current_lsn,
            wal_segment_name=post.current_wal_segment,
            database_size_bytes=envelope.plaintext_size_bytes,
            backup_duration_seconds=duration,
            encrypted=True,
            key_id=encryption_key_id,
            checksum_sha256=envelope.plaintext_sha256,
            ciphertext_sha256=envelope.ciphertext_sha256,
            manifest_sha256=manifest_sha,
            signer_fingerprint_sha256=fingerprint,
            storage_location=storage_location,
            storage_version=envelope.ciphertext_sha256,
            tool_versions={"pg_basebackup": manifest["tools"]["pg_basebackup"]},
        )
        return self._catalogue(metadata)

    def create_wal_archive(
        self,
        wal_path: Path,
        encryption_key_id: str,
        signing_key_path: Path,
        *,
        base_backup_id: str | None = None,
        wal_start_lsn: str = "",
        wal_end_lsn: str = "",
        archived_at: datetime | None = None,
    ) -> BackupMetadata:
        """Encrypt and sign one actual PostgreSQL WAL segment."""
        kms = self._require_crypto()
        wal_path = Path(wal_path)
        if not wal_path.is_file():
            raise FileNotFoundError(wal_path)

        base = (
            self._backups.get(base_backup_id)
            if base_backup_id
            else next(
                (
                    item
                    for item in self.list_backups()
                    if item.backup_type == BackupType.FULL
                ),
                None,
            )
        )
        if base is None or base.backup_type != BackupType.FULL:
            raise BackupCapabilityError(
                "WAL archival requires a known full backup for database identity"
            )

        segment_name = wal_path.name.upper()
        timeline, _ = wal_segment_index(segment_name, base.wal_segment_size_bytes)
        if timeline != base.timeline_id:
            raise BackupCapabilityError(
                "WAL timeline does not match the selected base backup"
            )
        if wal_path.stat().st_size != base.wal_segment_size_bytes:
            raise BackupCapabilityError(
                "WAL file size does not match the cluster WAL segment size"
            )

        plaintext_sha = _hash_file(wal_path)
        duplicates = [
            item
            for item in self._backups.values()
            if item.backup_type == BackupType.WAL
            and item.database_system_identifier == base.database_system_identifier
            and item.timeline_id == base.timeline_id
            and item.wal_segment_name == segment_name
        ]
        if duplicates:
            existing = duplicates[-1]
            if existing.checksum_sha256 != plaintext_sha:
                raise BackupCapabilityError(
                    "A different payload is already catalogued for this WAL segment"
                )
            return existing

        backup_id = new_id("wal")
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(mode=0o700)
        ciphertext = backup_dir / f"{segment_name}.we3enc"
        envelope = encrypt_file(
            wal_path,
            ciphertext,
            kms_client=kms,
            key_id=encryption_key_id,
            kms_identity=kms_identity(kms, encryption_key_id),
        )
        timestamp = archived_at or utc_now()
        storage_location = ciphertext.relative_to(self.backup_root).as_posix()
        manifest = {
            "schema_version": "we3.backup_manifest.v2",
            "backup_id": backup_id,
            "backup_type": BackupType.WAL.value,
            "created_at": timestamp.isoformat(),
            "database": {
                "name": base.database_name,
                "system_identifier": base.database_system_identifier,
                "timeline_id": base.timeline_id,
                "wal_segment_size_bytes": base.wal_segment_size_bytes,
                "wal_start_lsn": wal_start_lsn,
                "wal_end_lsn": wal_end_lsn,
                "wal_segment_name": segment_name,
            },
            "object": {
                "logical_name": segment_name,
                "storage_location": storage_location,
                "storage_version": envelope.ciphertext_sha256,
                "encryption": envelope.to_dict(),
            },
            "parent_base_backup_id": base.backup_id,
        }
        manifest_sha, fingerprint = self._write_manifest(
            backup_dir, manifest, signing_key_path
        )
        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=BackupType.WAL,
            backup_timestamp=timestamp,
            database_name=base.database_name,
            database_system_identifier=base.database_system_identifier,
            timeline_id=base.timeline_id,
            wal_segment_size_bytes=base.wal_segment_size_bytes,
            wal_start_lsn=wal_start_lsn,
            wal_end_lsn=wal_end_lsn,
            wal_segment_name=segment_name,
            database_size_bytes=envelope.plaintext_size_bytes,
            backup_duration_seconds=0.0,
            encrypted=True,
            key_id=encryption_key_id,
            checksum_sha256=envelope.plaintext_sha256,
            ciphertext_sha256=envelope.ciphertext_sha256,
            manifest_sha256=manifest_sha,
            signer_fingerprint_sha256=fingerprint,
            storage_location=storage_location,
            storage_version=envelope.ciphertext_sha256,
        )
        return self._catalogue(metadata)

    def verify_backup_integrity(self, backup_id: str) -> bool:
        """Verify catalogue, signed manifest, ciphertext, KMS unwrap, and AEAD tag."""
        metadata = self._backups.get(backup_id)
        if metadata is None or not metadata.encrypted:
            return False
        if self.kms_client is None or self.trust_registry is None:
            return False

        manifest_path, signature_path, ciphertext = self._manifest_paths(metadata)
        if not manifest_path.is_file() or not signature_path.is_file() or not ciphertext.is_file():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_bytes = canonical_json(manifest)
            if sha256_hex(manifest_bytes) != metadata.manifest_sha256:
                return False
            envelope = EncryptionEnvelope.from_dict(
                dict(manifest["object"]["encryption"])
            )
            signature = _signature_from_dict(
                json.loads(signature_path.read_text(encoding="utf-8"))
            )
            if (
                signature.public_key_fingerprint_sha256
                != metadata.signer_fingerprint_sha256
                or not self.trust_registry.is_trusted(
                    signature.public_key_fingerprint_sha256
                )
                or not verify_bytes(manifest_bytes, signature)
            ):
                return False
            if (
                str(manifest["backup_id"]) != metadata.backup_id
                or str(manifest["backup_type"]) != metadata.backup_type.value
                or str(manifest["object"]["storage_version"]) != metadata.storage_version
                or envelope.plaintext_sha256 != metadata.checksum_sha256
                or envelope.ciphertext_sha256 != metadata.ciphertext_sha256
                or envelope.key_id != metadata.key_id
                or not verify_ciphertext(ciphertext, envelope)
            ):
                return False

            with tempfile.TemporaryDirectory(
                prefix=".verify-", dir=self.backup_root
            ) as temporary:
                clear = Path(temporary) / "payload"
                decrypt_file(
                    ciphertext,
                    clear,
                    kms_client=self.kms_client,
                    envelope=envelope,
                )
        except Exception:
            return False

        metadata.verification_timestamp = utc_now()
        metadata.status = BackupStatus.VERIFIED
        self._save_catalog()
        return True

    def generate_restore_plan(
        self,
        target_timestamp: datetime,
        *,
        recovery_baseline: RecoveryBaseline,
        target_lsn: str | None = None,
    ) -> RestorePlan:
        """Build a restore plan only from continuous, verified, real WAL segments."""
        if self.trust_registry is None or not verify_recovery_baseline(
            recovery_baseline, self.trust_registry
        ):
            raise BackupCapabilityError(
                "Restore planning requires a signed recovery baseline from a trusted key"
            )

        full_backups = sorted(
            (
                item
                for item in self._backups.values()
                if item.backup_type == BackupType.FULL
                and item.backup_timestamp <= target_timestamp
                and item.encrypted
            ),
            key=lambda item: item.backup_timestamp,
        )
        if not full_backups:
            raise ValueError("No suitable full backup exists before the restore target")
        base = full_backups[-1]
        if not self.verify_backup_integrity(base.backup_id):
            raise BackupCapabilityError(
                f"Base backup {base.backup_id} failed integrity/trust verification"
            )

        if target_timestamp <= base.backup_timestamp and not target_lsn:
            selected_wal: list[BackupMetadata] = []
            coverage_end = base.backup_timestamp
        else:
            wal = sorted(
                (
                    item
                    for item in self._backups.values()
                    if item.backup_type == BackupType.WAL
                    and item.database_system_identifier
                    == base.database_system_identifier
                    and item.timeline_id == base.timeline_id
                    and item.wal_segment_size_bytes == base.wal_segment_size_bytes
                ),
                key=lambda item: wal_segment_index(
                    item.wal_segment_name, item.wal_segment_size_bytes
                )[1],
            )
            base_timeline, base_index = wal_segment_index(
                base.wal_segment_name, base.wal_segment_size_bytes
            )
            wal = [
                item
                for item in wal
                if wal_segment_index(
                    item.wal_segment_name, item.wal_segment_size_bytes
                )[0]
                == base_timeline
                and wal_segment_index(
                    item.wal_segment_name, item.wal_segment_size_bytes
                )[1]
                >= base_index
            ]
            if not wal:
                raise ValueError(
                    "No archived WAL coverage exists from the base backup segment"
                )
            if wal_segment_index(
                wal[0].wal_segment_name, wal[0].wal_segment_size_bytes
            )[1] != base_index:
                raise ValueError(
                    "Archived WAL coverage begins after the base backup segment"
                )
            if not wal_segments_are_contiguous(
                [item.wal_segment_name for item in wal],
                base.wal_segment_size_bytes,
            ):
                raise ValueError("Archived WAL coverage contains one or more gaps")

            selected_wal = []
            target_reached = False
            target_index = None
            if target_lsn:
                from .postgres import wal_segment_for_lsn

                target_name = wal_segment_for_lsn(
                    target_lsn, base.timeline_id, base.wal_segment_size_bytes
                )
                _, target_index = wal_segment_index(
                    target_name, base.wal_segment_size_bytes
                )
            for item in wal:
                if not self.verify_backup_integrity(item.backup_id):
                    raise BackupCapabilityError(
                        f"WAL backup {item.backup_id} failed integrity/trust verification"
                    )
                selected_wal.append(item)
                _, item_index = wal_segment_index(
                    item.wal_segment_name, item.wal_segment_size_bytes
                )
                if target_index is not None:
                    target_reached = item_index >= target_index
                else:
                    target_reached = item.backup_timestamp >= target_timestamp
                if target_reached:
                    break
            if not target_reached:
                raise ValueError(
                    "Archived WAL does not provide continuous coverage through the restore target"
                )
            coverage_end = selected_wal[-1].backup_timestamp

        sequence = [base.backup_id] + [item.backup_id for item in selected_wal]
        seed = sha256_hex(
            canonical_json(
                {
                    "target_timestamp": target_timestamp.isoformat(),
                    "target_lsn": target_lsn,
                    "sequence": sequence,
                    "baseline": recovery_baseline.payload_sha256,
                }
            )
        )
        plan = RestorePlan(
            plan_id=f"restore_{seed[:16]}",
            target_timestamp=target_timestamp,
            target_lsn=target_lsn,
            backup_sequence=sequence,
            wal_segments_needed=[item.wal_segment_name for item in selected_wal],
            estimated_restore_time_minutes=max(30, 30 + 10 * len(selected_wal)),
            isolated_environment=f"restore-{seed[:12]}",
            database_system_identifier=base.database_system_identifier,
            timeline_id=base.timeline_id,
            wal_segment_size_bytes=base.wal_segment_size_bytes,
            coverage_end_timestamp=coverage_end,
            recovery_baseline_sha256=recovery_baseline.payload_sha256,
        )
        plan_dir = self.backup_root / "restore-plans"
        plan_dir.mkdir(exist_ok=True)
        (plan_dir / f"{plan.plan_id}.json").write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return plan

    def list_backups(self, limit: int | None = None) -> list[BackupMetadata]:
        backups = sorted(
            self._backups.values(),
            key=lambda item: (item.backup_timestamp, item.backup_id),
            reverse=True,
        )
        return backups[:limit] if limit is not None else backups

    def get_backup(self, backup_id: str) -> BackupMetadata | None:
        return self._backups.get(backup_id)


class RecoveryOrchestrator:
    """Executes isolated physical restore/PITR and evidence reconciliation."""

    def __init__(
        self,
        backup_manager: BackupManager,
        database_url: str,
        *,
        trust_registry: TrustRegistry,
    ) -> None:
        self.backup_manager = backup_manager
        self.database_url = database_url
        self.trust_registry = trust_registry

    def reconcile_restored_state(
        self,
        isolated_database_url: str,
        *,
        expected: RecoveryBaseline,
        signing_key_path: Path | None = None,
    ) -> ReconciliationReport:
        """Compare restored state with a trusted baseline using the actual schema."""
        if not verify_recovery_baseline(expected, self.trust_registry):
            raise BackupCapabilityError("Recovery baseline signature/trust validation failed")

        engine_url = (
            sqlalchemy_postgresql_url(isolated_database_url)
            if isolated_database_url.startswith(
                ("postgresql://", "postgres://", "postgresql+psycopg://")
            )
            else isolated_database_url
        )
        engine = create_engine(engine_url, poolclass=NullPool, future=True)
        discrepancies: list[str] = []
        try:
            with engine.connect() as conn:
                audit_valid, audit_roots = _audit_rows_from_connection(conn)
                total_runs = _table_count(conn, "runs")
                total_classifications = _table_count(conn, "classifications")
                metric_snapshots = _table_count(conn, "metric_snapshots")
                gate_decisions = _table_count(conn, "gate_decisions")
                provenance_edges = _table_count(conn, "provenance_edges")
                outbox_pending = int(
                    conn.execute(
                        sql_text(
                            "SELECT COUNT(*) FROM outbox_events WHERE status <> 'delivered'"
                        )
                    ).scalar_one()
                )
        finally:
            engine.dispose()

        comparisons = [
            ("runs", total_runs, expected.total_runs),
            ("classifications", total_classifications, expected.total_classifications),
            ("metric_snapshots", metric_snapshots, expected.metric_snapshots),
            ("gate_decisions", gate_decisions, expected.gate_decisions),
            ("provenance_edges", provenance_edges, expected.provenance_edges),
            ("outbox_pending", outbox_pending, expected.outbox_pending),
        ]
        for name, actual, wanted in comparisons:
            if actual != wanted:
                discrepancies.append(f"{name}: restored={actual}, expected={wanted}")
        if audit_roots != expected.audit_roots:
            discrepancies.append("audit chain roots do not match the signed baseline")
        if not audit_valid:
            discrepancies.append("cryptographic audit-chain verification failed")

        report = ReconciliationReport(
            report_id=new_id("recon"),
            restored_timestamp=utc_now(),
            verified_timestamp=utc_now(),
            total_runs=total_runs,
            runs_matched=min(total_runs, expected.total_runs),
            runs_missing=max(expected.total_runs - total_runs, 0),
            total_classifications=total_classifications,
            classifications_matched=min(
                total_classifications, expected.total_classifications
            ),
            audit_chain_valid=audit_valid,
            outbox_events_pending=outbox_pending,
            metric_snapshots_matched=min(
                metric_snapshots, expected.metric_snapshots
            ),
            gate_decisions_matched=min(gate_decisions, expected.gate_decisions),
            provenance_edges_matched=min(
                provenance_edges, expected.provenance_edges
            ),
            discrepancies=discrepancies,
            baseline_sha256=expected.payload_sha256,
        )
        if signing_key_path:
            payload = canonical_json(report.to_dict())
            report.reconciliation_signature = sign_bytes(
                payload, load_private_key(signing_key_path)
            )
        return report

    def execute_isolated_restore(
        self,
        plan: RestorePlan,
        isolated_database_url: str,
        *,
        data_directory: Path,
        recovery_baseline: RecoveryBaseline,
        signing_key_path: Path | None = None,
        startup_timeout_seconds: int = 120,
    ) -> RestoreExecutionResult:
        """Restore, replay, reconcile, stop, and retain measured recovery evidence."""
        if plan.recovery_baseline_sha256 != recovery_baseline.payload_sha256:
            raise BackupCapabilityError(
                "Restore plan and supplied recovery baseline do not match"
            )
        if not verify_recovery_baseline(recovery_baseline, self.trust_registry):
            raise BackupCapabilityError("Recovery baseline is not signed by a trusted key")
        if self.backup_manager.kms_client is None:
            raise BackupCapabilityError("Restore requires the configured backup KMS")

        connection = parse_postgresql_url(isolated_database_url)
        try:
            address = ipaddress.ip_address(connection.host)
            loopback = address.is_loopback
        except ValueError:
            loopback = connection.host.lower() == "localhost"
        if not loopback:
            raise BackupCapabilityError(
                "Isolated restore may only bind/connect through loopback"
            )

        data_directory = Path(data_directory)
        if data_directory.exists() and any(data_directory.iterdir()):
            raise BackupCapabilityError(
                f"Restore data directory must be empty: {data_directory}"
            )
        if data_directory.exists():
            data_directory.rmdir()

        pg_ctl = require_pg_tool("pg_ctl")
        require_pg_tool("postgres")
        started_at = utc_now()
        monotonic_start = time.monotonic()
        evidence_root = self.backup_manager.backup_root / "restore-evidence" / plan.plan_id
        evidence_root.mkdir(parents=True, exist_ok=False)
        log_path = evidence_root / "postgres.log"
        wal_archive = evidence_root / "wal"
        wal_archive.mkdir()
        pg_started = False

        try:
            base = self.backup_manager.get_backup(plan.backup_sequence[0])
            if base is None or base.backup_type != BackupType.FULL:
                raise BackupCapabilityError("Restore plan does not begin with a full backup")
            if (
                base.database_system_identifier != plan.database_system_identifier
                or base.timeline_id != plan.timeline_id
            ):
                raise BackupCapabilityError("Restore plan database identity mismatch")
            if not self.backup_manager.verify_backup_integrity(base.backup_id):
                raise BackupCapabilityError("Base backup failed verification before restore")

            manifest_path, _, encrypted_base = self.backup_manager._manifest_paths(base)
            base_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            base_envelope = EncryptionEnvelope.from_dict(
                dict(base_manifest["object"]["encryption"])
            )
            with tempfile.TemporaryDirectory(
                prefix=".restore-", dir=self.backup_manager.backup_root
            ) as temporary:
                base_tar = Path(temporary) / "base.tar"
                decrypt_file(
                    encrypted_base,
                    base_tar,
                    kms_client=self.backup_manager.kms_client,
                    envelope=base_envelope,
                )
                _safe_extract_physical_backup(base_tar, data_directory)

            for backup_id in plan.backup_sequence[1:]:
                wal = self.backup_manager.get_backup(backup_id)
                if wal is None or wal.backup_type != BackupType.WAL:
                    raise BackupCapabilityError(
                        f"Restore plan references invalid WAL backup {backup_id}"
                    )
                if not self.backup_manager.verify_backup_integrity(wal.backup_id):
                    raise BackupCapabilityError(
                        f"WAL backup {wal.backup_id} failed verification before restore"
                    )
                manifest_path, _, encrypted_wal = self.backup_manager._manifest_paths(wal)
                wal_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                wal_envelope = EncryptionEnvelope.from_dict(
                    dict(wal_manifest["object"]["encryption"])
                )
                decrypt_file(
                    encrypted_wal,
                    wal_archive / wal.wal_segment_name,
                    kms_client=self.backup_manager.kms_client,
                    envelope=wal_envelope,
                )

            restore_source = str((wal_archive / "%f").resolve())
            if "'" in restore_source:
                raise BackupCapabilityError(
                    "Restore archive path cannot contain a single quote"
                )
            auto_conf = data_directory / "postgresql.auto.conf"
            with auto_conf.open("a", encoding="utf-8") as handle:
                handle.write(f"\nrestore_command = 'cp {restore_source} %p'\n")
                if plan.target_lsn:
                    handle.write(f"recovery_target_lsn = '{plan.target_lsn}'\n")
                else:
                    target = plan.target_timestamp.isoformat()
                    handle.write(f"recovery_target_time = '{target}'\n")
                handle.write("recovery_target_action = 'promote'\n")
                handle.write("recovery_target_inclusive = 'true'\n")
            (data_directory / "recovery.signal").touch()
            data_directory.chmod(0o700)

            start = subprocess.run(
                [
                    pg_ctl,
                    "-D",
                    str(data_directory),
                    "-l",
                    str(log_path),
                    "-o",
                    f"-h 127.0.0.1 -p {connection.port}",
                    "-w",
                    "-t",
                    str(startup_timeout_seconds),
                    "start",
                ],
                capture_output=True,
                text=True,
            )
            if start.returncode != 0:
                raise BackupCapabilityError(
                    "Restored PostgreSQL failed to start: "
                    + (start.stderr.strip() or start.stdout.strip())
                )
            pg_started = True

            deadline = time.monotonic() + startup_timeout_seconds
            restored_engine = create_engine(
                sqlalchemy_postgresql_url(isolated_database_url),
                poolclass=NullPool,
                future=True,
            )
            try:
                while True:
                    with restored_engine.connect() as conn:
                        in_recovery = bool(
                            conn.execute(sql_text("SELECT pg_is_in_recovery()" )).scalar_one()
                        )
                    if not in_recovery:
                        break
                    if time.monotonic() >= deadline:
                        raise BackupCapabilityError(
                            "Restored PostgreSQL did not reach/promote the PITR target in time"
                        )
                    time.sleep(0.5)
            finally:
                restored_engine.dispose()

            report = self.reconcile_restored_state(
                isolated_database_url,
                expected=recovery_baseline,
                signing_key_path=signing_key_path,
            )
            success = report.to_dict()["status"] == "pass"
            if not success:
                raise BackupCapabilityError(
                    "Post-restore reconciliation did not match the signed baseline"
                )
        finally:
            if pg_started:
                subprocess.run(
                    [pg_ctl, "-D", str(data_directory), "-m", "fast", "-w", "stop"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

        completed_at = utc_now()
        duration = time.monotonic() - monotonic_start
        evidence_path = evidence_root / "restore_execution.json"
        result = RestoreExecutionResult(
            success=True,
            plan_id=plan.plan_id,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=duration,
            data_directory=str(data_directory.resolve()),
            wal_archive_directory=str(wal_archive.resolve()),
            postgres_version=tool_version("postgres"),
            pg_ctl_version=tool_version("pg_ctl"),
            log_sha256=_hash_file(log_path) if log_path.exists() else sha256_hex(b""),
            reconciliation=report.to_dict(),
            evidence_path=str(evidence_path.resolve()),
        )
        evidence_path.write_text(
            json.dumps(
                {
                    "schema_version": "we3.restore_execution.v1",
                    **result.to_dict(),
                    "configured_rto_hours": self.backup_manager.RTO_HOURS,
                    "configured_rpo_minutes": self.backup_manager.RPO_MINUTES,
                    "runtime_claim_note": (
                        "duration_seconds is measured evidence for this exercise; "
                        "configured RPO/RTO values are targets, not automatically proven."
                    ),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return result


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
        return {
            "trusted_fingerprints": sorted(
                getattr(trust_registry, "_trusted_fingerprints", set())
            ),
            "revoked_fingerprints": sorted(
                getattr(trust_registry, "_revoked_fingerprints", set())
            ),
            "backup_purpose": backup_key_purpose.value,
        }


def create_recovery_verification_manifest(
    backup_ids: list[str],
    restore_timestamp: datetime,
    reconciliation_report: ReconciliationReport,
    approvers: list[str],
) -> dict[str, Any]:
    distinct_approvers = sorted(set(approvers))
    required = 2
    report_status = reconciliation_report.to_dict()["status"]
    return {
        "schema_version": "we3.recovery_manifest.v2",
        "generated_at": utc_now().isoformat(),
        "backup_sequence": list(backup_ids),
        "restore_timestamp": restore_timestamp.isoformat(),
        "reconciliation_status": report_status,
        "approvals": {
            "required": required,
            "received": len(distinct_approvers),
            "approvers": distinct_approvers,
        },
        "re_certification_required": (
            report_status != "pass" or len(distinct_approvers) < required
        ),
    }


__all__ = [
    "BackupCapabilityError",
    "BackupMetadata",
    "BackupStatus",
    "BackupType",
    "KeyBackupManager",
    "ReconciliationReport",
    "RecoveryBaseline",
    "RecoveryOrchestrator",
    "RestoreExecutionResult",
    "RestorePlan",
    "capture_recovery_baseline",
    "create_recovery_verification_manifest",
    "verify_recovery_baseline",
]
