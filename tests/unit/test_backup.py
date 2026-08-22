"""Unit tests for encrypted backup identity, trust, catalogue, and WAL planning."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wilson_eval3ngine.backup.backup_manager import (
    BackupManager,
    BackupMetadata,
    BackupStatus,
    BackupType,
    RecoveryBaseline,
    create_recovery_verification_manifest,
    verify_recovery_baseline,
)
from wilson_eval3ngine.backup.crypto import (
    BackupEncryptionError,
    decrypt_file,
    encrypt_file,
)
from wilson_eval3ngine.backup.kms import AWSKMSClient, kms_identity
from wilson_eval3ngine.backup.postgres import (
    PostgreSQLBackupError,
    parse_postgresql_url,
    wal_segment_for_lsn,
    wal_segment_index,
    wal_segments_are_contiguous,
)
from wilson_eval3ngine.security.signing import (
    TrustRegistry,
    generate_private_key,
    load_private_key,
    sign_bytes,
)
from wilson_eval3ngine.storage.encrypted_store import LocalKMSClient
from wilson_eval3ngine.util import canonical_json, sha256_hex


TEST_MASTER_KEY = b"K" * 32
SEGMENT_SIZE = 1024 * 1024
BASE_SEGMENT = "000000010000000000000001"


class FakeAWSKMS:
    def generate_data_key(self, **kwargs):
        assert kwargs == {"KeyId": "alias/we3-backup", "KeySpec": "AES_256"}
        return {"Plaintext": b"D" * 32, "CiphertextBlob": b"wrapped"}

    def encrypt(self, **kwargs):
        return {"CiphertextBlob": b"cipher:" + kwargs["Plaintext"]}

    def decrypt(self, **kwargs):
        if kwargs["CiphertextBlob"] == b"wrapped":
            return {"Plaintext": b"D" * 32}
        return {"Plaintext": kwargs["CiphertextBlob"].removeprefix(b"cipher:")}

    def describe_key(self, **kwargs):
        assert kwargs["KeyId"] == "alias/we3-backup"
        return {
            "KeyMetadata": {
                "KeyId": "1234abcd",
                "Arn": "arn:aws:kms:us-east-1:111122223333:key/1234abcd",
                "KeyManager": "CUSTOMER",
                "Origin": "AWS_KMS",
                "MultiRegion": False,
            }
        }


def _signed_baseline(key_path: Path, registry: TrustRegistry) -> RecoveryBaseline:
    payload = {
        "schema_version": "we3.recovery_baseline.v1",
        "captured_at": "2026-08-22T00:00:00+00:00",
        "total_runs": 1,
        "total_classifications": 1,
        "metric_snapshots": 1,
        "gate_decisions": 1,
        "provenance_edges": 1,
        "outbox_pending": 0,
        "audit_roots": {},
    }
    envelope = sign_bytes(canonical_json(payload), load_private_key(key_path))
    registry.trust_key(envelope.public_key_fingerprint_sha256)
    return RecoveryBaseline(
        captured_at=payload["captured_at"],
        total_runs=1,
        total_classifications=1,
        metric_snapshots=1,
        gate_decisions=1,
        provenance_edges=1,
        outbox_pending=0,
        audit_roots={},
        payload_sha256=sha256_hex(canonical_json(payload)),
        signature=envelope.to_dict(),
    )


def _catalogued_full_backup(
    manager: BackupManager,
    key_path: Path,
    registry: TrustRegistry,
    *,
    timestamp: datetime,
) -> BackupMetadata:
    backup_id = "backup_full_test"
    backup_dir = manager.backup_root / backup_id
    backup_dir.mkdir()
    plaintext = backup_dir / "plain.tar"
    plaintext.write_bytes(b"physical-backup-payload")
    ciphertext = backup_dir / "base.tar.we3enc"
    assert manager.kms_client is not None
    envelope = encrypt_file(
        plaintext,
        ciphertext,
        kms_client=manager.kms_client,
        key_id="test-kms-key",
        kms_identity=kms_identity(manager.kms_client, "test-kms-key"),
    )
    plaintext.unlink()
    storage_location = ciphertext.relative_to(manager.backup_root).as_posix()
    manifest = {
        "schema_version": "we3.backup_manifest.v2",
        "backup_id": backup_id,
        "backup_type": "full",
        "created_at": timestamp.isoformat(),
        "database": {
            "name": "we3",
            "system_identifier": "system-123",
            "timeline_id": 1,
            "wal_segment_size_bytes": SEGMENT_SIZE,
            "wal_start_lsn": "0/100000",
            "wal_end_lsn": "0/180000",
            "wal_end_segment": BASE_SEGMENT,
            "server_version": "16.4",
        },
        "object": {
            "logical_name": "base.tar",
            "storage_location": storage_location,
            "storage_version": envelope.ciphertext_sha256,
            "encryption": envelope.to_dict(),
        },
        "tools": {"pg_basebackup": "pg_basebackup (PostgreSQL) 16.4"},
    }
    manifest_sha, fingerprint = manager._write_manifest(
        backup_dir, manifest, key_path
    )
    registry.trust_key(fingerprint)
    return manager._catalogue(
        BackupMetadata(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            backup_timestamp=timestamp,
            database_name="we3",
            database_system_identifier="system-123",
            timeline_id=1,
            wal_segment_size_bytes=SEGMENT_SIZE,
            wal_start_lsn="0/100000",
            wal_end_lsn="0/180000",
            wal_segment_name=BASE_SEGMENT,
            database_size_bytes=envelope.plaintext_size_bytes,
            backup_duration_seconds=1.2,
            encrypted=True,
            key_id="test-kms-key",
            checksum_sha256=envelope.plaintext_sha256,
            ciphertext_sha256=envelope.ciphertext_sha256,
            manifest_sha256=manifest_sha,
            signer_fingerprint_sha256=fingerprint,
            storage_location=storage_location,
            storage_version=envelope.ciphertext_sha256,
            status=BackupStatus.COMPLETED,
        )
    )


def test_streaming_encryption_round_trip_and_tamper_detection(tmp_path: Path) -> None:
    kms = LocalKMSClient(master_key=TEST_MASTER_KEY)
    source = tmp_path / "source"
    encrypted = tmp_path / "encrypted"
    restored = tmp_path / "restored"
    source.write_bytes((b"backup-data-" * 200_000) + b"end")

    envelope = encrypt_file(
        source,
        encrypted,
        kms_client=kms,
        key_id="local-test-key",
        kms_identity={"provider": "local-test"},
    )
    assert envelope.algorithm == "AES-256-GCM"
    assert envelope.plaintext_sha256 == sha256_hex(source.read_bytes())

    decrypt_file(encrypted, restored, kms_client=kms, envelope=envelope)
    assert restored.read_bytes() == source.read_bytes()

    payload = bytearray(encrypted.read_bytes())
    payload[len(payload) // 2] ^= 1
    encrypted.write_bytes(payload)
    with pytest.raises(BackupEncryptionError):
        decrypt_file(encrypted, tmp_path / "tampered", kms_client=kms, envelope=envelope)


def test_aws_kms_adapter_records_resolved_non_secret_identity() -> None:
    kms = AWSKMSClient(client=FakeAWSKMS())
    plain, wrapped = kms.generate_data_key("alias/we3-backup")
    assert plain == b"D" * 32
    assert wrapped == b"wrapped"
    assert kms.decrypt("alias/we3-backup", wrapped) == plain
    identity = kms.key_metadata("alias/we3-backup")
    assert identity["requested_key_id"] == "alias/we3-backup"
    assert identity["resolved_key_id"] == "1234abcd"
    assert "Plaintext" not in identity


def test_postgresql_url_validation_rejects_sqlite() -> None:
    with pytest.raises(PostgreSQLBackupError, match="PostgreSQL"):
        parse_postgresql_url("sqlite:///var/we3.db")
    parsed = parse_postgresql_url(
        "postgresql://we3:secret@127.0.0.1:55432/wilson_eval3ngine"
    )
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 55432
    assert parsed.database == "wilson_eval3ngine"
    assert parsed.subprocess_env()["PGPASSWORD"] == "secret"


def test_wal_sequence_helpers_detect_gaps_and_target_segment() -> None:
    first = "000000010000000000000001"
    second = "000000010000000000000002"
    fourth = "000000010000000000000004"
    assert wal_segment_index(second, SEGMENT_SIZE)[1] == (
        wal_segment_index(first, SEGMENT_SIZE)[1] + 1
    )
    assert wal_segments_are_contiguous([first, second], SEGMENT_SIZE)
    assert not wal_segments_are_contiguous([first, fourth], SEGMENT_SIZE)
    assert wal_segment_for_lsn("0/180000", 1, SEGMENT_SIZE) == first


def test_signed_baseline_requires_hash_signature_and_trust(tmp_path: Path) -> None:
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    baseline = _signed_baseline(key, registry)
    assert verify_recovery_baseline(baseline, registry)

    untrusted = TrustRegistry()
    assert not verify_recovery_baseline(baseline, untrusted)

    changed = replace(baseline, total_runs=baseline.total_runs + 1)
    assert not verify_recovery_baseline(changed, registry)


def test_catalogue_survives_restart_and_deep_verification(tmp_path: Path) -> None:
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    kms = LocalKMSClient(master_key=TEST_MASTER_KEY)
    manager = BackupManager(
        "postgresql://localhost/we3",
        tmp_path / "backups",
        kms_client=kms,
        trust_registry=registry,
    )
    metadata = _catalogued_full_backup(
        manager,
        key,
        registry,
        timestamp=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )
    assert manager.verify_backup_integrity(metadata.backup_id)

    reloaded = BackupManager(
        "postgresql://localhost/we3",
        tmp_path / "backups",
        kms_client=kms,
        trust_registry=registry,
    )
    assert [item.backup_id for item in reloaded.list_backups()] == [
        metadata.backup_id
    ]
    assert reloaded.verify_backup_integrity(metadata.backup_id)


def test_manifest_or_ciphertext_mutation_is_rejected(tmp_path: Path) -> None:
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    manager = BackupManager(
        "postgresql://localhost/we3",
        tmp_path / "backups",
        kms_client=LocalKMSClient(master_key=TEST_MASTER_KEY),
        trust_registry=registry,
    )
    metadata = _catalogued_full_backup(
        manager,
        key,
        registry,
        timestamp=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )
    manifest, _, ciphertext = manager._manifest_paths(metadata)

    original_manifest = manifest.read_text(encoding="utf-8")
    parsed = json.loads(original_manifest)
    parsed["database"]["name"] = "tampered"
    manifest.write_text(json.dumps(parsed), encoding="utf-8")
    assert not manager.verify_backup_integrity(metadata.backup_id)

    manifest.write_text(original_manifest, encoding="utf-8")
    raw = bytearray(ciphertext.read_bytes())
    raw[0] ^= 1
    ciphertext.write_bytes(raw)
    assert not manager.verify_backup_integrity(metadata.backup_id)


def test_restore_plan_uses_real_contiguous_wal_and_signed_baseline(
    tmp_path: Path,
) -> None:
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    kms = LocalKMSClient(master_key=TEST_MASTER_KEY)
    manager = BackupManager(
        "postgresql://localhost/we3",
        tmp_path / "backups",
        kms_client=kms,
        trust_registry=registry,
    )
    base_time = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    base = _catalogued_full_backup(manager, key, registry, timestamp=base_time)
    baseline = _signed_baseline(key, registry)

    wal1 = tmp_path / BASE_SEGMENT
    wal1.write_bytes(b"A" * SEGMENT_SIZE)
    first = manager.create_wal_archive(
        wal1,
        "test-kms-key",
        key,
        base_backup_id=base.backup_id,
        archived_at=base_time + timedelta(minutes=5),
    )
    wal2_name = "000000010000000000000002"
    wal2 = tmp_path / wal2_name
    wal2.write_bytes(b"B" * SEGMENT_SIZE)
    second = manager.create_wal_archive(
        wal2,
        "test-kms-key",
        key,
        base_backup_id=base.backup_id,
        archived_at=base_time + timedelta(minutes=10),
    )

    plan = manager.generate_restore_plan(
        base_time + timedelta(minutes=7),
        recovery_baseline=baseline,
    )
    assert plan.backup_sequence == [base.backup_id, first.backup_id, second.backup_id]
    assert plan.wal_segments_needed == [BASE_SEGMENT, wal2_name]
    assert not any(name.startswith("segment_") for name in plan.wal_segments_needed)


def test_restore_plan_rejects_missing_base_segment(tmp_path: Path) -> None:
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    manager = BackupManager(
        "postgresql://localhost/we3",
        tmp_path / "backups",
        kms_client=LocalKMSClient(master_key=TEST_MASTER_KEY),
        trust_registry=registry,
    )
    base_time = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    base = _catalogued_full_backup(manager, key, registry, timestamp=base_time)
    baseline = _signed_baseline(key, registry)

    later = tmp_path / "000000010000000000000002"
    later.write_bytes(b"B" * SEGMENT_SIZE)
    manager.create_wal_archive(
        later,
        "test-kms-key",
        key,
        base_backup_id=base.backup_id,
        archived_at=base_time + timedelta(minutes=10),
    )
    with pytest.raises(ValueError, match="begins after"):
        manager.generate_restore_plan(
            base_time + timedelta(minutes=7),
            recovery_baseline=baseline,
        )


def test_recovery_manifest_requires_two_distinct_approvers() -> None:
    from wilson_eval3ngine.backup.backup_manager import ReconciliationReport

    report = ReconciliationReport(
        report_id="r",
        restored_timestamp=datetime.now(timezone.utc),
        verified_timestamp=datetime.now(timezone.utc),
        total_runs=1,
        runs_matched=1,
        runs_missing=0,
        total_classifications=1,
        classifications_matched=1,
        audit_chain_valid=True,
        outbox_events_pending=0,
        metric_snapshots_matched=1,
        gate_decisions_matched=1,
        provenance_edges_matched=1,
    )
    manifest = create_recovery_verification_manifest(
        ["backup"],
        datetime.now(timezone.utc),
        report,
        ["alice", "alice"],
    )
    assert manifest["approvals"]["received"] == 1
    assert manifest["re_certification_required"] is True
