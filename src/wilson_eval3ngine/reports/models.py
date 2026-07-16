"""
Canonical report models for TODO 47.

T7.1.3 - Build reproducible reports and governed exports.
Produces deterministic, verifiable reports that reconcile across all formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExportState(str, Enum):
    """Export operation states per TODO 47 requirement."""
    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CanonicalReport:
    """Immutable canonical report model built from experiment outcomes.

    This is the single source of truth for report serialization.
    All serializers (JSON, HTML, CSV, Parquet) derive from this model
    without re-calculating results.
    """
    schema_version: str = "we3.canonical_report.v1"
    experiment_id: str = ""
    project_id: str = ""
    generated_at: str = ""
    manifest_hash: str = ""
    dataset_hash: str = ""
    source_snapshot_times: dict[str, str] = field(default_factory=dict)
    metric_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    gate_statuses: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    artifact_hashes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to deterministic dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "project_id": self.project_id,
            "generated_at": self.generated_at,
            "manifest_hash": self.manifest_hash,
            "dataset_hash": self.dataset_hash,
            "source_snapshot_times": dict(sorted(self.source_snapshot_times.items())),
            "metric_values": dict(sorted(self.metric_values.items())),
            "gate_statuses": dict(sorted(self.gate_statuses.items())),
            "limitations": list(self.limitations),
            "artifact_hashes": sorted(self.artifact_hashes),
        }

    def compute_report_hash(self) -> str:
        """Compute deterministic hash of the canonical report content."""
        from ..util import sha256_hex
        return sha256_hex(self.to_dict())


@dataclass
class ExportRequest:
    """Export request model with state tracking."""
    export_id: str = ""
    export_type: str = ""  # dossier, report, raw_evidence
    resource_id: str = ""
    project_id: str = ""
    requester_id: str = ""
    state: ExportState = ExportState.REQUESTED
    created_at: str = ""
    updated_at: str = ""
    expires_at: str | None = None
    output_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "we3.export_request.v1",
            "export_id": self.export_id,
            "export_type": self.export_type,
            "resource_id": self.resource_id,
            "project_id": self.project_id,
            "requester_id": self.requester_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "output_path": self.output_path,
            "report_hash": None,
        }


__all__ = [
    "ExportState",
    "CanonicalReport",
    "ExportRequest",
]