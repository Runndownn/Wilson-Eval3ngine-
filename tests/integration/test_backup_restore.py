"""Authorized disposable PostgreSQL backup -> WAL -> PITR -> reconcile exercise.

The module is skipped during ordinary unit/test runs. CI's dedicated recovery
job sets ``WE3_RUN_POSTGRES_RECOVERY_TEST=1`` and installs PostgreSQL binaries,
so this becomes real runtime evidence rather than a mock of pg_basebackup or
pg_ctl.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from wilson_eval3ngine.backup.backup_manager import (
    BackupManager,
    RecoveryOrchestrator,
    capture_recovery_baseline,
)
from wilson_eval3ngine.backup.postgres import (
    require_pg_tool,
    wal_segment_for_lsn,
    wal_segment_index,
)
from wilson_eval3ngine.persistence.audit import compute_audit_event_hash
from wilson_eval3ngine.security.signing import TrustRegistry, generate_private_key
from wilson_eval3ngine.storage.encrypted_store import LocalKMSClient


pytestmark = pytest.mark.runtime

if os.environ.get("WE3_RUN_POSTGRES_RECOVERY_TEST") != "1":
    pytest.skip(
        "real PostgreSQL recovery exercise requires WE3_RUN_POSTGRES_RECOVERY_TEST=1",
        allow_module_level=True,
    )


SOURCE_PORT = 55432
RESTORE_PORT = 55433
MASTER_KEY = b"R" * 32


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        check=check,
        text=True,
        capture_output=True,
    )


def _create_recovery_schema(database_url: str) -> None:
    engine = create_engine(
        database_url.replace("postgresql://", "postgresql+psycopg://", 1),
        poolclass=NullPool,
        future=True,
    )
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"))
            conn.execute(
                text(
                    "CREATE TABLE classifications "
                    "(id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE audit_events ("
                    "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, "
                    "event_type TEXT NOT NULL, aggregate_type TEXT NOT NULL, "
                    "aggregate_id TEXT NOT NULL, actor_id TEXT NOT NULL, "
                    "payload_json JSONB NOT NULL, previous_hash TEXT, "
                    "event_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)"
                )
            )
            conn.execute(text("CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"))
            conn.execute(
                text(
                    "CREATE TABLE provenance_edges "
                    "(id TEXT PRIMARY KEY, edge_hash TEXT NOT NULL)"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE outbox_events "
                    "(id TEXT PRIMARY KEY, status TEXT NOT NULL)"
                )
            )

            occurred_at = datetime.now(timezone.utc)
            payload = {"kind": "runtime-recovery-seed"}
            event_hash = compute_audit_event_hash(
                event_id="audit-1",
                project_id="project-runtime",
                event_type="run.completed",
                aggregate_type="run",
                aggregate_id="run-1",
                actor_id="runtime-test",
                payload=payload,
                previous_hash=None,
                occurred_at=occurred_at,
            )
            conn.execute(text("INSERT INTO runs VALUES ('run-1', 'completed')"))
            conn.execute(
                text("INSERT INTO classifications VALUES ('class-1', 'run-1', NULL)")
            )
            conn.execute(text("INSERT INTO metric_snapshots VALUES ('metric-1')"))
            conn.execute(text("INSERT INTO gate_decisions VALUES ('gate-1')"))
            conn.execute(
                text("INSERT INTO provenance_edges VALUES ('edge-1', 'edge-hash-1')")
            )
            conn.execute(
                text("INSERT INTO outbox_events VALUES ('outbox-1', 'delivered')")
            )
            conn.execute(
                text(
                    """
                    INSERT INTO audit_events (
                        id, project_id, event_type, aggregate_type, aggregate_id,
                        actor_id, payload_json, previous_hash, event_hash, created_at
                    ) VALUES (
                        'audit-1', 'project-runtime', 'run.completed', 'run',
                        'run-1', 'runtime-test', CAST(:payload AS JSONB), NULL,
                        :event_hash, :created_at
                    )
                    """
                ),
                {
                    "payload": json.dumps(payload, separators=(",", ":")),
                    "event_hash": event_hash,
                    "created_at": occurred_at,
                },
            )
    finally:
        engine.dispose()


def _mutate_to_target(database_url: str) -> str:
    engine = create_engine(
        database_url.replace("postgresql://", "postgresql+psycopg://", 1),
        poolclass=NullPool,
        future=True,
    )
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO runs VALUES ('run-2', 'completed')"))
            conn.execute(
                text("INSERT INTO classifications VALUES ('class-2', 'run-2', NULL)")
            )
            conn.execute(text("INSERT INTO metric_snapshots VALUES ('metric-2')"))
            conn.execute(text("INSERT INTO gate_decisions VALUES ('gate-2')"))
            conn.execute(
                text("INSERT INTO provenance_edges VALUES ('edge-2', 'edge-hash-2')")
            )
            conn.execute(
                text("INSERT INTO outbox_events VALUES ('outbox-2', 'delivered')")
            )
        with engine.connect() as conn:
            return str(
                conn.execute(text("SELECT pg_current_wal_lsn()::text")).scalar_one()
            )
    finally:
        engine.dispose()


def _switch_wal(database_url: str) -> None:
    engine = create_engine(
        database_url.replace("postgresql://", "postgresql+psycopg://", 1),
        poolclass=NullPool,
        future=True,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_switch_wal()"))
            conn.commit()
    finally:
        engine.dispose()


def _wait_for(path: Path, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for PostgreSQL archive file: {path}")


def test_real_encrypted_postgres_backup_pitr_and_reconciliation(tmp_path: Path) -> None:
    initdb = require_pg_tool("initdb")
    pg_ctl = require_pg_tool("pg_ctl")
    source_data = tmp_path / "source-data"
    archive_dir = tmp_path / "wal-archive"
    archive_dir.mkdir()
    backup_root = tmp_path / "encrypted-backups"
    restore_data = tmp_path / "restore-data"

    _run(
        initdb,
        "-D",
        str(source_data),
        "--username=postgres",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-locale",
    )
    if "'" in str(archive_dir.resolve()):
        pytest.fail("pytest temporary archive path unexpectedly contains a quote")
    with (source_data / "postgresql.conf").open("a", encoding="utf-8") as handle:
        handle.write("\nlisten_addresses = '127.0.0.1'\n")
        handle.write(f"port = {SOURCE_PORT}\n")
        handle.write("wal_level = 'replica'\n")
        handle.write("archive_mode = 'on'\n")
        handle.write(
            f"archive_command = 'test ! -f {archive_dir.resolve()}/%f "
            f"&& cp %p {archive_dir.resolve()}/%f'\n"
        )

    source_log = tmp_path / "source-postgres.log"
    _run(
        pg_ctl,
        "-D",
        str(source_data),
        "-l",
        str(source_log),
        "-w",
        "start",
    )
    source_url = f"postgresql://postgres@127.0.0.1:{SOURCE_PORT}/postgres"
    restore_url = f"postgresql://postgres@127.0.0.1:{RESTORE_PORT}/postgres"

    try:
        _create_recovery_schema(source_url)
        signing_key = generate_private_key(tmp_path / "recovery-signing.pem")
        registry = TrustRegistry()
        manager = BackupManager(
            source_url,
            backup_root,
            kms_client=LocalKMSClient(master_key=MASTER_KEY),
            trust_registry=registry,
        )

        full = manager.create_full_backup("runtime-local-kms", signing_key)
        registry.trust_key(full.signer_fingerprint_sha256)
        assert manager.verify_backup_integrity(full.backup_id)

        target_lsn = _mutate_to_target(source_url)
        baseline = capture_recovery_baseline(
            source_url,
            signing_key_path=signing_key,
        )
        assert baseline.signature
        registry.trust_key(baseline.signature["public_key_fingerprint_sha256"])

        _switch_wal(source_url)
        first_archive = archive_dir / full.wal_segment_name
        _wait_for(first_archive)

        base_index = wal_segment_index(
            full.wal_segment_name, full.wal_segment_size_bytes
        )[1]
        target_segment = wal_segment_for_lsn(
            target_lsn, full.timeline_id, full.wal_segment_size_bytes
        )
        target_index = wal_segment_index(
            target_segment, full.wal_segment_size_bytes
        )[1]
        archived = []
        for path in sorted(archive_dir.iterdir()):
            if len(path.name) != 24:
                continue
            _, index = wal_segment_index(path.name, full.wal_segment_size_bytes)
            if base_index <= index <= target_index:
                archived.append(
                    manager.create_wal_archive(
                        path,
                        "runtime-local-kms",
                        signing_key,
                        base_backup_id=full.backup_id,
                    )
                )
        assert archived, "the base WAL segment must have been archived"

        saved = dict(manager._backups)
        manager._backups = {
            key: value
            for key, value in manager._backups.items()
            if value.backup_type.value != "wal"
        }
        with pytest.raises(ValueError, match="WAL coverage"):
            manager.generate_restore_plan(
                datetime.now(timezone.utc),
                recovery_baseline=baseline,
                target_lsn=target_lsn,
            )
        manager._backups = saved

        signature_path = backup_root / full.backup_id / "manifest.sig.json"
        original_signature = signature_path.read_text(encoding="utf-8")
        forged = json.loads(original_signature)
        forged["signature_base64"] = "AAAA"
        signature_path.write_text(json.dumps(forged), encoding="utf-8")
        assert manager.verify_backup_integrity(full.backup_id) is False
        signature_path.write_text(original_signature, encoding="utf-8")
        assert manager.verify_backup_integrity(full.backup_id) is True

        ciphertext = backup_root / full.storage_location
        with ciphertext.open("r+b") as handle:
            first_byte = handle.read(1)
            handle.seek(0)
            handle.write(bytes([first_byte[0] ^ 1]))
            handle.flush()
            os.fsync(handle.fileno())
        assert manager.verify_backup_integrity(full.backup_id) is False
        with ciphertext.open("r+b") as handle:
            handle.seek(0)
            handle.write(first_byte)
            handle.flush()
            os.fsync(handle.fileno())
        assert manager.verify_backup_integrity(full.backup_id) is True

        plan = manager.generate_restore_plan(
            datetime.now(timezone.utc),
            recovery_baseline=baseline,
            target_lsn=target_lsn,
        )
        result = RecoveryOrchestrator(
            manager,
            source_url,
            trust_registry=registry,
        ).execute_isolated_restore(
            plan,
            restore_url,
            data_directory=restore_data,
            recovery_baseline=baseline,
            signing_key_path=signing_key,
        )

        assert result.success is True
        assert result.reconciliation["status"] == "pass"
        assert result.duration_seconds > 0
        assert Path(result.evidence_path).is_file()
    finally:
        _run(
            pg_ctl,
            "-D",
            str(source_data),
            "-m",
            "fast",
            "-w",
            "stop",
            check=False,
        )
