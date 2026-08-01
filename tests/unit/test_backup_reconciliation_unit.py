"""Unit tests for backup reconciliation and signing."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wilson_eval3ngine.backup.backup_manager import (
    RecoveryOrchestrator,
    ReconciliationReport,
)
from wilson_eval3ngine.security.signing import (
    generate_private_key,
    load_private_key,
    sign_bytes,
    verify_bytes,
)


class TestReconciliationReport:
    def test_to_dict_contains_all_fields(self):
        report = ReconciliationReport(
            report_id="recon_123",
            restored_timestamp=datetime(2026, 1, 1, 12, 0, 0),
            verified_timestamp=datetime(2026, 1, 1, 12, 1, 0),
            total_runs=100,
            runs_matched=95,
            runs_missing=5,
            total_classifications=500,
            classifications_matched=498,
            audit_chain_valid=True,
            outbox_events_pending=0,
            metric_snapshots_matched=10,
            gate_decisions_matched=8,
            provenance_edges_matched=15,
        )

        d = report.to_dict()
        assert d["report_id"] == "recon_123"
        assert d["totals"]["runs"] == 100
        assert d["totals"]["classifications"] == 500
        assert d["totals"]["audit_chain_valid"] is True
        assert d["totals"]["outbox_events_pending"] == 0
        assert d["matched"]["runs"] == 95
        assert d["matched"]["classifications"] == 498
        assert d["missing"]["runs"] == 5
        assert d["status"] == "fail"  # runs_missing > 0

    def test_to_dict_passes_when_all_good(self):
        report = ReconciliationReport(
            report_id="recon_123",
            restored_timestamp=datetime(2026, 1, 1, 12, 0, 0),
            verified_timestamp=datetime(2026, 1, 1, 12, 1, 0),
            total_runs=100,
            runs_matched=100,
            runs_missing=0,
            total_classifications=500,
            classifications_matched=500,
            audit_chain_valid=True,
            outbox_events_pending=0,
            metric_snapshots_matched=10,
            gate_decisions_matched=8,
            provenance_edges_matched=15,
        )

        d = report.to_dict()
        assert d["status"] == "pass"

    def test_to_dict_includes_signature_when_present(self):
        from wilson_eval3ngine.security.signing import SignatureEnvelope

        report = ReconciliationReport(
            report_id="recon_123",
            restored_timestamp=datetime(2026, 1, 1, 12, 0, 0),
            verified_timestamp=datetime(2026, 1, 1, 12, 1, 0),
            total_runs=100,
            runs_matched=100,
            runs_missing=0,
            total_classifications=500,
            classifications_matched=500,
            audit_chain_valid=True,
            outbox_events_pending=0,
            metric_snapshots_matched=10,
            gate_decisions_matched=8,
            provenance_edges_matched=15,
        )

        # Add a mock signature
        report.reconciliation_signature = SignatureEnvelope(
            algorithm="Ed25519",
            public_key_fingerprint_sha256="abc123",
            public_key_pem="mock_pem",
            signature_base64="mock_sig",
        )

        d = report.to_dict()
        assert "signature" in d
        assert d["signature"]["algorithm"] == "Ed25519"


class TestBackupReconciliation:
    def test_reconcile_empty_database(self, tmp_path):
        """Test reconciliation against an empty database."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "empty.db"
        db_url = f"sqlite:///{db_path}"

        # Create tables
        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))
            conn.commit()
        engine.dispose()

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)

        report = manager.reconcile_restored_state(db_url)

        assert report.total_runs == 0
        assert report.runs_matched == 0
        assert report.runs_missing == 0
        assert report.total_classifications == 0
        assert report.classifications_matched == 0
        assert report.audit_chain_valid is True
        assert report.outbox_events_pending == 0
        assert report.metric_snapshots_matched == 0
        assert report.gate_decisions_matched == 0
        assert report.provenance_edges_matched == 0
        assert report.to_dict()["status"] == "pass"

    def test_reconcile_with_data(self, tmp_path):
        """Test reconciliation against a database with data."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Create tables and insert data
        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))

            # Insert test data
            conn.execute(sql_text(
                "INSERT INTO runs (id, state) VALUES ('run1', 'completed')"
            ))
            conn.execute(sql_text(
                "INSERT INTO runs (id, state) VALUES ('run2', 'failed')"
            ))
            conn.execute(sql_text(
                "INSERT INTO classifications (id, run_id, superseded_by_id) "
                "VALUES ('cls1', 'run1', NULL)"
            ))
            conn.execute(sql_text(
                "INSERT INTO classifications (id, run_id, superseded_by_id) "
                "VALUES ('cls2', 'run1', 'cls3')"
            ))
            conn.execute(sql_text(
                "INSERT INTO audit_events (id, event_hash, payload_json) "
                "VALUES ('evt1', 'hash1', '{\"lineage\": \"parent\"}')"
            ))
            conn.execute(sql_text(
                "INSERT INTO metric_snapshots (id) VALUES ('snap1')"
            ))
            conn.execute(sql_text(
                "INSERT INTO gate_decisions (id) VALUES ('gate1')"
            ))
            conn.commit()
        engine.dispose()

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)
        report = manager.reconcile_restored_state(db_url)

        assert report.total_runs == 2
        assert report.runs_matched == 1  # only 'completed'
        assert report.runs_missing == 1
        assert report.total_classifications == 2
        assert report.classifications_matched == 1  # only non-superseded
        assert report.audit_chain_valid is True
        assert report.metric_snapshots_matched == 1
        assert report.gate_decisions_matched == 1
        assert report.provenance_edges_matched == 1
        assert report.to_dict()["status"] == "fail"  # runs_missing > 0

    def test_reconcile_with_broken_audit_chain(self, tmp_path):
        """Test reconciliation detects broken audit chain."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))

            # Insert audit event with empty hash (broken chain)
            conn.execute(sql_text(
                "INSERT INTO audit_events (id, event_hash, payload_json) "
                "VALUES ('evt1', '', '{}')"
            ))
            conn.commit()
        engine.dispose()

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)
        report = manager.reconcile_restored_state(db_url)

        assert report.audit_chain_valid is False

    def test_reconcile_with_outbox_pending(self, tmp_path):
        """Test reconciliation detects pending outbox events."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))

            # Insert audit event with unprocessed flag
            conn.execute(sql_text(
                "INSERT INTO audit_events (id, event_hash, payload_json) "
                "VALUES ('evt1', 'hash1', '{\"processed\": false}')"
            ))
            conn.commit()
        engine.dispose()

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)
        report = manager.reconcile_restored_state(db_url)

        assert report.outbox_events_pending == 1


class TestBackupSigning:
    def test_reconcile_with_signing(self, tmp_path):
        """Test that reconciliation report is signed when key path provided."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Create empty database
        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))
            conn.commit()
        engine.dispose()

        # Generate signing key
        key_path = tmp_path / "signing_key.pem"
        generate_private_key(key_path)

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)
        report = manager.reconcile_restored_state(db_url, signing_key_path=key_path)

        # Verify signature was added
        assert report.reconciliation_signature is not None
        assert report.reconciliation_signature.algorithm == "Ed25519"

        # Verify signature is valid
        payload = json.dumps(report.to_dict(), sort_keys=True).encode("utf-8")
        # Remove signature from dict for verification
        report_dict = report.to_dict()
        del report_dict["signature"]
        payload = json.dumps(report_dict, sort_keys=True).encode("utf-8")
        assert verify_bytes(payload, report.reconciliation_signature) is True

    def test_reconcile_without_signing_key(self, tmp_path):
        """Test that reconciliation works without signing key."""
        from sqlalchemy import create_engine, text as sql_text
        from sqlalchemy.pool import NullPool

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url, poolclass=NullPool, future=True)
        with engine.connect() as conn:
            conn.execute(sql_text(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, state TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE classifications ("
                "id TEXT PRIMARY KEY, run_id TEXT, superseded_by_id TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE audit_events ("
                "id TEXT PRIMARY KEY, event_hash TEXT, payload_json TEXT)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE metric_snapshots (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE gate_decisions (id TEXT PRIMARY KEY)"
            ))
            conn.execute(sql_text(
                "CREATE TABLE overrides (id TEXT PRIMARY KEY, resource_type TEXT, "
                "active BOOLEAN, payload_json TEXT)"
            ))
            conn.commit()
        engine.dispose()

        manager = RecoveryOrchestrator.__new__(RecoveryOrchestrator)
        report = manager.reconcile_restored_state(db_url, signing_key_path=None)

        assert report.reconciliation_signature is None
