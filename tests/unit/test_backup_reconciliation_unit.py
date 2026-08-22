"""Reconciliation tests against the real audit/outbox/provenance schema contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from wilson_eval3ngine.backup.backup_manager import (
    BackupCapabilityError,
    BackupManager,
    RecoveryOrchestrator,
    capture_recovery_baseline,
)
from wilson_eval3ngine.persistence.audit import compute_audit_event_hash
from wilson_eval3ngine.security.signing import TrustRegistry, generate_private_key


def _schema(url: str) -> None:
    engine = create_engine(url, poolclass=NullPool, future=True)
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
                    "payload_json JSON NOT NULL, previous_hash TEXT, "
                    "event_hash TEXT NOT NULL, created_at TIMESTAMP NOT NULL)"
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
    finally:
        engine.dispose()


def _insert_consistent_state(url: str) -> str:
    occurred_at = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    payload = {"lineage": "source"}
    event_hash = compute_audit_event_hash(
        event_id="audit-1",
        project_id="project-a",
        event_type="run.completed",
        aggregate_type="run",
        aggregate_id="run-1",
        actor_id="worker-a",
        payload=payload,
        previous_hash=None,
        occurred_at=occurred_at,
    )
    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO runs VALUES ('run-1', 'completed')"))
            conn.execute(
                text(
                    "INSERT INTO classifications VALUES "
                    "('class-1', 'run-1', NULL)"
                )
            )
            conn.execute(text("INSERT INTO metric_snapshots VALUES ('metric-1')"))
            conn.execute(text("INSERT INTO gate_decisions VALUES ('gate-1')"))
            conn.execute(
                text(
                    "INSERT INTO provenance_edges VALUES "
                    "('edge-1', 'edge-hash-1')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO outbox_events VALUES "
                    "('outbox-1', 'delivered')"
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO audit_events (
                        id, project_id, event_type, aggregate_type, aggregate_id,
                        actor_id, payload_json, previous_hash, event_hash, created_at
                    ) VALUES (
                        :id, :project, :event_type, :aggregate_type, :aggregate_id,
                        :actor, :payload, NULL, :event_hash, :created_at
                    )
                    """
                ),
                {
                    "id": "audit-1",
                    "project": "project-a",
                    "event_type": "run.completed",
                    "aggregate_type": "run",
                    "aggregate_id": "run-1",
                    "actor": "worker-a",
                    "payload": '{"lineage":"source"}',
                    "event_hash": event_hash,
                    "created_at": occurred_at.replace(tzinfo=None),
                },
            )
    finally:
        engine.dispose()
    return event_hash


def _orchestrator(tmp_path: Path, url: str, registry: TrustRegistry):
    manager = BackupManager(url, tmp_path / "backups", trust_registry=registry)
    return RecoveryOrchestrator(manager, url, trust_registry=registry)


def test_reconciliation_reads_real_outbox_provenance_and_audit_tables(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'restore.db'}"
    _schema(url)
    event_hash = _insert_consistent_state(url)
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()

    baseline = capture_recovery_baseline(url, signing_key_path=key)
    assert baseline.audit_roots == {"project-a": event_hash}
    assert baseline.outbox_pending == 0
    assert baseline.provenance_edges == 1
    assert baseline.signature
    registry.trust_key(baseline.signature["public_key_fingerprint_sha256"])

    report = _orchestrator(tmp_path, url, registry).reconcile_restored_state(
        url,
        expected=baseline,
        signing_key_path=key,
    )
    assert report.to_dict()["status"] == "pass"
    assert report.audit_chain_valid is True
    assert report.outbox_events_pending == 0
    assert report.provenance_edges_matched == 1
    assert report.reconciliation_signature is not None


def test_reconciliation_detects_pending_outbox_in_actual_outbox_table(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'restore.db'}"
    _schema(url)
    _insert_consistent_state(url)
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    baseline = capture_recovery_baseline(url, signing_key_path=key)
    assert baseline.signature
    registry.trust_key(baseline.signature["public_key_fingerprint_sha256"])

    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE outbox_events SET status='pending' WHERE id='outbox-1'")
            )
    finally:
        engine.dispose()

    report = _orchestrator(tmp_path, url, registry).reconcile_restored_state(
        url, expected=baseline
    )
    assert report.outbox_events_pending == 1
    assert report.to_dict()["status"] == "fail"
    assert any("outbox_pending" in item for item in report.discrepancies)


def test_reconciliation_recomputes_audit_chain_cryptographically(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'restore.db'}"
    _schema(url)
    _insert_consistent_state(url)
    key = generate_private_key(tmp_path / "signing.pem")
    registry = TrustRegistry()
    baseline = capture_recovery_baseline(url, signing_key_path=key)
    assert baseline.signature
    registry.trust_key(baseline.signature["public_key_fingerprint_sha256"])

    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE audit_events SET event_hash='not-the-canonical-hash' "
                    "WHERE id='audit-1'"
                )
            )
    finally:
        engine.dispose()

    report = _orchestrator(tmp_path, url, registry).reconcile_restored_state(
        url, expected=baseline
    )
    assert report.audit_chain_valid is False
    assert report.to_dict()["status"] == "fail"
    assert "cryptographic audit-chain verification failed" in report.discrepancies


def test_baseline_capture_refuses_broken_audit_chain(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'restore.db'}"
    _schema(url)
    _insert_consistent_state(url)
    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit_events SET previous_hash='forged'"))
    finally:
        engine.dispose()

    key = generate_private_key(tmp_path / "signing.pem")
    with pytest.raises(BackupCapabilityError, match="audit chain"):
        capture_recovery_baseline(url, signing_key_path=key)


def test_reconciliation_requires_trusted_baseline(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'restore.db'}"
    _schema(url)
    _insert_consistent_state(url)
    key = generate_private_key(tmp_path / "signing.pem")
    baseline = capture_recovery_baseline(url, signing_key_path=key)

    with pytest.raises(BackupCapabilityError, match="signature/trust"):
        _orchestrator(tmp_path, url, TrustRegistry()).reconcile_restored_state(
            url, expected=baseline
        )
