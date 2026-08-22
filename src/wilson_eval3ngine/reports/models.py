"""Canonical report models for reproducible reports and governed exports.

Every serializer derives from these immutable result structures so exported
formats reconcile to the same evidence instead of recalculating outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExportState(str, Enum):
    """Lifecycle states for a governed export operation."""

    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CanonicalReport:
    """Immutable source of truth for report serialization."""

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
        """Convert to a deterministic dictionary for serialization."""
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
        """Compute the deterministic hash of canonical report content."""
        from ..util import sha256_hex

        return sha256_hex(self.to_dict())


@dataclass
class ExportRequest:
    """Governed export request with explicit lifecycle state."""

    export_id: str = ""
    export_type: str = ""
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


__all__ = ["ExportState", "CanonicalReport", "ExportRequest"]
