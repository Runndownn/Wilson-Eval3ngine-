"""Provenance edge model linking source material through release evidence.

T3.1.4 - Provenance, transactional outbox, and audit linkage.
Defines typed source/target IDs, versions, hashes, and relationship types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..util import new_id, sha256_hex, utc_now


class ProvenanceEdgeType(StrEnum):
    """Types of provenance relationships between entities.

    The chain represents:
    source -> case -> expectation -> run -> attempt -> response -> classification
           -> review -> metric_snapshot -> gate -> dossier
    """
    SOURCE_TO_CASE = "source_to_case"
    CASE_TO_EXPECTATION = "case_to_expectation"
    EXPECTATION_TO_RUN = "expectation_to_run"
    RUN_TO_ATTEMPT = "run_to_attempt"
    ATTEMPT_TO_RESPONSE = "attempt_to_response"
    RESPONSE_TO_CLASSIFICATION = "response_to_classification"
    CLASSIFICATION_TO_REVIEW = "classification_to_review"
    REVIEW_TO_METRIC = "review_to_metric"
    METRIC_TO_SNAPSHOT = "metric_to_snapshot"
    SNAPSHOT_TO_GATE = "snapshot_to_gate"
    GATE_TO_DOSSIER = "gate_to_dossier"


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    """Immutable link between two entities in the evaluation chain.

    Each edge captures the relationship with:
    - Typed source/target IDs and versions
    - Content hashes for integrity verification
    - Immutable edge hash for tamper detection
    - Correlation ID for end-to-end tracing
    - Creation actor/process for audit trail
    """
    edge_id: str = field(default_factory=lambda: new_id("edge"))
    source_id: str = ""
    source_type: str = ""
    source_version: str = ""
    source_hash: str = ""
    target_id: str = ""
    target_type: str = ""
    target_version: str = ""
    target_hash: str = ""
    edge_type: ProvenanceEdgeType = ProvenanceEdgeType.SOURCE_TO_CASE
    edge_hash: str = ""
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    actor_id: str = ""
    correlation_id: str = ""

    def __post_init__(self) -> None:
        if not self.edge_hash:
            object.__setattr__(self, 'edge_hash', sha256_hex({
                "source_id": self.source_id,
                "source_type": self.source_type,
                "source_version": self.source_version,
                "source_hash": self.source_hash,
                "target_id": self.target_id,
                "target_type": self.target_type,
                "target_version": self.target_version,
                "target_hash": self.target_hash,
                "edge_type": self.edge_type.value,
                "created_at": self.created_at,
                "actor_id": self.actor_id,
                "correlation_id": self.correlation_id,
            }))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_version": self.source_version,
            "source_hash": self.source_hash,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "target_version": self.target_version,
            "target_hash": self.target_hash,
            "edge_type": self.edge_type.value,
            "edge_hash": self.edge_hash,
            "created_at": self.created_at,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
        }


def build_provenance_chain(
    entities: list[tuple[str, str, str]],
    correlation_id: str = "",
    actor_id: str = "",
) -> list[ProvenanceEdge]:
    """Build a provenance chain from sequential entities.

    Args:
        entities: List of (id, type, version) tuples in order
        correlation_id: Optional correlation ID for end-to-end tracing
        actor_id: Optional actor ID for audit trail

    Returns:
        List of provenance edges linking consecutive entities
    """
    edges = []
    for i in range(len(entities) - 1):
        source_id, source_type, source_version = entities[i]
        target_id, target_type, target_version = entities[i + 1]

        # Determine edge type based on position in chain
        edge_type = _edge_type_for_transition(source_type, target_type)

        edges.append(ProvenanceEdge(
            source_id=source_id,
            source_type=source_type,
            source_version=source_version,
            source_hash="",  # Filled at verification time
            target_id=target_id,
            target_type=target_type,
            target_version=target_version,
            target_hash="",  # Filled at verification time
            edge_type=edge_type,
            correlation_id=correlation_id,
            actor_id=actor_id,
        ))

    return edges


def _edge_type_for_transition(source_type: str, target_type: str) -> ProvenanceEdgeType:
    """Determine edge type from source/target type transition."""
    transitions = {
        ("source", "case"): ProvenanceEdgeType.SOURCE_TO_CASE,
        ("case", "expectation"): ProvenanceEdgeType.CASE_TO_EXPECTATION,
        ("expectation", "run"): ProvenanceEdgeType.EXPECTATION_TO_RUN,
        ("run", "attempt"): ProvenanceEdgeType.RUN_TO_ATTEMPT,
        ("attempt", "response"): ProvenanceEdgeType.ATTEMPT_TO_RESPONSE,
        ("response", "classification"): ProvenanceEdgeType.RESPONSE_TO_CLASSIFICATION,
        ("classification", "review"): ProvenanceEdgeType.CLASSIFICATION_TO_REVIEW,
        ("review", "metric_snapshot"): ProvenanceEdgeType.REVIEW_TO_METRIC,
        ("metric_snapshot", "gate"): ProvenanceEdgeType.METRIC_TO_SNAPSHOT,
        ("snapshot", "gate"): ProvenanceEdgeType.SNAPSHOT_TO_GATE,
        ("gate", "dossier"): ProvenanceEdgeType.GATE_TO_DOSSIER,
    }
    return transitions.get((source_type, target_type), ProvenanceEdgeType.SOURCE_TO_CASE)


__all__ = [
    "ProvenanceEdgeType",
    "ProvenanceEdge",
    "build_provenance_chain",
]