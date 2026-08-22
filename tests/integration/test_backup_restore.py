"""Integration-oriented tests for the provisional backup/recovery boundary.

These tests deliberately avoid pretending that a simulated record is a real
PostgreSQL restore. Native encrypted backup/WAL/restore execution must fail
closed until the production implementation is wired; metadata/catalogue,
content integrity, and restore planning remain deterministic and testable.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from wilson_eval3ngine.backup.backup_manager import (
    BackupCapabilityError,
    BackupManager,
    BackupMetadata,
    BackupStatus,
    BackupType,
    RecoveryOrchestrator,
)


def _metadata(
    backup_id: str,
    backup_type: BackupType,
    timestamp: datetime,
    *,
    checksum: str = "external-content-sha256",
    wal_start_lsn: str = "0/1000000",
    wal_end_lsn: str = "0/2000000",
) -> BackupMetadata:
    return BackupMetadata(
        backup_id=backup_id,
        backup_type=backup_type,
        backup_timestamp=timestamp,
        database_name="wilson_eval3ngine",
        database_size_bytes=1024,
        wal_start_lsn=wal_start_lsn,
        wal_end_lsn=wal_end_lsn,
        backup_duration_seconds=1.0,
        encrypted=False,
        key_id="",
        checksum_sha256=checksum,
        status=BackupStatus.COMPLETED,
    )


def _expected_single_file_digest(name: str, payload: bytes) -> str:
    digest = hashlib.sha256()
    encoded_name = name.encode("utf-8")
    digest.update(len(encoded_name).to_bytes(8, "big"))
    digest.update(encoded_name)
    digest.update(payload)
    return digest.hexdigest()


def test_native_encrypted_backup_creation_fails_closed(tmp_path) -> None:
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    with pytest.raises(BackupCapabilityError, match="not yet implemented"):
        manager.create_full_backup("kms-key")


def test_native_wal_archive_fails_closed(tmp_path) -> None:
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    with pytest.raises(BackupCapabilityError, match="not yet implemented"):
        manager.create_wal_archive("kms-key")


def test_external_backup_catalogue_survives_manager_restart(tmp_path) -> None:
    timestamp = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    manager.register_external_backup(_metadata("backup_full_001", BackupType.FULL, timestamp))

    reloaded = BackupManager("postgresql://localhost/test", tmp_path)
    backups = reloaded.list_backups()
    assert [item.backup_id for item in backups] == ["backup_full_001"]


def test_restore_plan_rejects_missing_wal_coverage(tmp_path) -> None:
    timestamp = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    manager.register_external_backup(_metadata("backup_full_001", BackupType.FULL, timestamp))

    with pytest.raises(ValueError, match="No verified WAL coverage"):
        manager.generate_restore_plan(timestamp + timedelta(minutes=15))


def test_restore_plan_uses_only_recorded_wal_ids(tmp_path) -> None:
    base_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    wal_time = base_time + timedelta(minutes=10)
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    manager.register_external_backup(_metadata("backup_full_001", BackupType.FULL, base_time))
    manager.register_external_backup(
        _metadata(
            "wal_001",
            BackupType.WAL,
            wal_time,
            wal_start_lsn="0/2000000",
            wal_end_lsn="0/3000000",
        )
    )

    plan = manager.generate_restore_plan(wal_time)
    assert plan.backup_sequence == ["backup_full_001", "wal_001"]
    assert plan.wal_segments_needed == ["wal_001"]
    assert not any(segment.startswith("segment_") for segment in plan.wal_segments_needed)


def test_content_integrity_detects_backup_mutation(tmp_path) -> None:
    backup_id = "backup_local_001"
    backup_dir = tmp_path / backup_id
    backup_dir.mkdir()
    payload = b"verified-backup-content"
    (backup_dir / "base.tar").write_bytes(payload)

    metadata = _metadata(
        backup_id,
        BackupType.FULL,
        datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
        checksum=_expected_single_file_digest("base.tar", payload),
    )
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    manager.register_external_backup(metadata, local_backup_path=backup_dir)
    assert manager.verify_backup_integrity(backup_id) is True

    (backup_dir / "base.tar").write_bytes(payload + b"-tampered")
    assert manager.verify_backup_integrity(backup_id) is False


def test_signature_verification_request_fails_closed(tmp_path) -> None:
    backup_id = "backup_signed_001"
    backup_dir = tmp_path / backup_id
    backup_dir.mkdir()
    payload = b"backup"
    (backup_dir / "base.tar").write_bytes(payload)
    metadata = _metadata(
        backup_id,
        BackupType.FULL,
        datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
        checksum=_expected_single_file_digest("base.tar", payload),
    )
    metadata.signature_sha256 = "declared-signature"

    manager = BackupManager("postgresql://localhost/test", tmp_path)
    manager.register_external_backup(metadata, local_backup_path=backup_dir)
    assert manager.verify_backup_integrity(backup_id) is False


def test_isolated_restore_execution_fails_closed(tmp_path) -> None:
    manager = BackupManager("postgresql://localhost/test", tmp_path)
    orchestrator = RecoveryOrchestrator(manager, "postgresql://localhost/test")
    base_time = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    manager.register_external_backup(_metadata("backup_full_001", BackupType.FULL, base_time))
    plan = manager.generate_restore_plan(base_time)

    with pytest.raises(BackupCapabilityError, match="not yet implemented"):
        orchestrator.execute_isolated_restore(plan, "postgresql://localhost/restored")
