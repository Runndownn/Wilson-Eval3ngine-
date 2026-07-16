"""Tests for transactional outbox and provenance linkage.

T3.1.4 - Provenance, transactional outbox, and audit linkage.
"""

from __future__ import annotations

import pytest

from wilson_eval3ngine.persistence.outbox import (
    Outbox,
    OutboxEvent,
    OutboxEventType,
)
from wilson_eval3ngine.domain.provenance import (
    ProvenanceEdge,
    ProvenanceEdgeType,
)


class TestOutboxEventEnvelope:
    """Test suite for outbox event envelope."""

    def test_event_envelope_has_required_fields(self):
        """Event envelope contains all required fields."""
        event = OutboxEvent(
            event_id="evt_test_001",
            aggregate_id="agg_test_001",
            aggregate_type="experiment",
            project_id="proj_test",
            event_type=OutboxEventType.EXPERIMENT_CREATED,
            payload={"key": "value"},
        )
        assert event.event_id == "evt_test_001"
        assert event.payload_hash != ""
        # trace_id defaults to empty, but to_dict() provides fallback
        event_dict = event.to_dict()
        assert event_dict["trace_id"] == event.event_id

    def test_event_payload_hash_computed(self):
        """Payload hash is computed deterministically."""
        event1 = OutboxEvent(
            event_id="evt_1",
            aggregate_id="agg_1",
            aggregate_type="experiment",
            project_id="proj_test",
            event_type=OutboxEventType.EXPERIMENT_CREATED,
            payload={"name": "test"},
        )
        event2 = OutboxEvent(
            event_id="evt_1",
            aggregate_id="agg_1",
            aggregate_type="experiment",
            project_id="proj_test",
            event_type=OutboxEventType.EXPERIMENT_CREATED,
            payload={"name": "test"},
        )
        assert event1.payload_hash == event2.payload_hash


class TestOutboxEventType:
    """Test suite for outbox event types."""

    def test_all_event_types_exist(self):
        """All required event types are defined."""
        assert OutboxEventType.EXPERIMENT_CREATED.value == "experiment.created"
        assert OutboxEventType.RUN_STARTED.value == "run.started"
        assert OutboxEventType.RUN_COMPLETED.value == "run.completed"
        assert OutboxEventType.CLASSIFICATION_RECORDED.value == "classification.recorded"
        assert OutboxEventType.GATE_EVALUATED.value == "gate.evaluated"
        assert OutboxEventType.DOSSIER_GENERATED.value == "dossier.generated"


class TestProvenanceEdge:
    """Test suite for provenance edge model."""

    def test_provenance_edge_has_immutable_hash(self):
        """Provenance edge computes immutable edge hash."""
        edge = ProvenanceEdge(
            edge_id="edge_001",
            source_id="src_001",
            source_type="case",
            source_version="1.0.0",
            source_hash="abc123",
            target_id="tgt_001",
            target_type="expectation",
            target_version="1.0.0",
            target_hash="def456",
            edge_type=ProvenanceEdgeType.CASE_TO_EXPECTATION,
            actor_id="test_actor",
            correlation_id="corr_001",
        )
        assert edge.edge_hash != ""
        assert len(edge.edge_hash) == 64  # SHA-256 hex length
        assert edge.edge_id != ""

    def test_provenance_edge_default_values(self):
        """Provenance edge has sensible defaults."""
        edge = ProvenanceEdge()
        assert edge.edge_id != ""
        assert edge.edge_type == ProvenanceEdgeType.SOURCE_TO_CASE
        assert edge.created_at != ""
        assert edge.edge_hash != ""  # Computed even with empty values

    def test_provenance_edge_to_dict(self):
        """Provenance edge serializes correctly."""
        edge = ProvenanceEdge(
            edge_id="edge_002",
            source_id="src_002",
            source_type="source",
            source_version="1.0.0",
            source_hash="hash_a",
            target_id="tgt_002",
            target_type="case",
            target_version="1.0.0",
            target_hash="hash_b",
            edge_type=ProvenanceEdgeType.SOURCE_TO_CASE,
            actor_id="system",
            correlation_id="corr_xyz",
        )
        d = edge.to_dict()
        assert d["edge_id"] == "edge_002"
        assert d["source_id"] == "src_002"
        assert d["edge_type"] == "source_to_case"
        assert d["actor_id"] == "system"
        assert d["correlation_id"] == "corr_xyz"


class TestBuildProvenanceChain:
    """Test suite for provenance chain building."""

    def test_build_chain_creates_edges(self):
        """Building a chain creates edges between consecutive entities."""
        from wilson_eval3ngine.domain.provenance import build_provenance_chain

        chain = build_provenance_chain([
            ("src_001", "source", "1.0.0"),
            ("case_001", "case", "1.0.0"),
            ("exp_001", "expectation", "1.0.0"),
        ])
        assert len(chain) == 2
        assert chain[0].source_type == "source"
        assert chain[0].target_type == "case"
        assert chain[1].source_type == "case"
        assert chain[1].target_type == "expectation"


class TestProvenanceEdgeType:
    """Test suite for provenance edge types."""

    def test_all_edge_types_exist(self):
        """All required edge types are defined."""
        assert ProvenanceEdgeType.SOURCE_TO_CASE.value == "source_to_case"
        assert ProvenanceEdgeType.CASE_TO_EXPECTATION.value == "case_to_expectation"
        assert ProvenanceEdgeType.EXPECTATION_TO_RUN.value == "expectation_to_run"
        assert ProvenanceEdgeType.RUN_TO_ATTEMPT.value == "run_to_attempt"
        assert ProvenanceEdgeType.ATTEMPT_TO_RESPONSE.value == "attempt_to_response"
        assert ProvenanceEdgeType.RESPONSE_TO_CLASSIFICATION.value == "response_to_classification"
        assert ProvenanceEdgeType.CLASSIFICATION_TO_REVIEW.value == "classification_to_review"
        assert ProvenanceEdgeType.REVIEW_TO_METRIC.value == "review_to_metric"
        assert ProvenanceEdgeType.METRIC_TO_SNAPSHOT.value == "metric_to_snapshot"
        assert ProvenanceEdgeType.SNAPSHOT_TO_GATE.value == "snapshot_to_gate"
        assert ProvenanceEdgeType.GATE_TO_DOSSIER.value == "gate_to_dossier"