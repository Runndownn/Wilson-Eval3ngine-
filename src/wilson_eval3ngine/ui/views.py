"""Persona-specific view models with explicit evidence and scope boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..reports.models import CanonicalReport


@dataclass(frozen=True, slots=True)
class ExecutiveSummary:
    """Aggregate-only executive view containing no raw evidence."""

    schema_version: str = "we3.executive_summary.v1"
    experiment_id: str = ""
    project_id: str = ""
    release_status: str = "pending"
    critical_blocks: list[str] = field(default_factory=list)
    # Unknown aggregates are represented as None rather than fabricated 100%/0%.
    support_percentage: float | None = None
    uncertainty_percentage: float | None = None
    cost_usd: float = 0.0
    freshness_hours: float = 0.0
    last_refresh_at: str = ""
    source_snapshot_hash: str = ""


@dataclass(frozen=True, slots=True)
class AnalystView:
    """Project-scoped analyst drill-down with evidence lineage."""

    schema_version: str = "we3.analyst_view.v1"
    experiment_id: str = ""
    project_id: str = ""
    slices: list[dict[str, Any]] = field(default_factory=list)
    cases: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    grades: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    version_context: dict[str, str] = field(default_factory=dict)
    freshness_state: str = "fresh"


@dataclass(frozen=True, slots=True)
class ReviewerQueueItem:
    """Redacted reviewer task. Raw evidence requires a separate reveal flow."""

    schema_version: str = "we3.reviewer_queue_item.v1"
    case_id: str = ""
    experiment_id: str = ""
    task_type: str = ""
    version: str = ""
    sla_deadline: str = ""
    redacted_evidence: str = ""
    classification_hint: str = ""
    priority: str = "normal"
    assigned_reviewer: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRevealRequest:
    """Auditable request to reveal restricted evidence."""

    schema_version: str = "we3.evidence_reveal.v1"
    case_id: str = ""
    reviewer_id: str = ""
    justification: str = ""
    approval_ticket: str = ""
    audit_trail: list[str] = field(default_factory=list)


def build_executive_summary(
    report: CanonicalReport,
    *,
    cost_usd: float = 0.0,
    freshness_hours: float = 0.0,
) -> ExecutiveSummary:
    """Build an aggregate-only summary from canonical evidence.

    Support and uncertainty remain ``None`` until the canonical report contains
    an authoritative aggregate contract for those concepts. Missing evidence is
    never converted into an optimistic value.
    """
    if cost_usd < 0:
        raise ValueError("cost_usd must be non-negative")
    if freshness_hours < 0:
        raise ValueError("freshness_hours must be non-negative")

    statuses = tuple(report.gate_statuses.values())
    if not statuses:
        release_status = "indeterminate"
    elif "block" in statuses:
        release_status = "block"
    elif "indeterminate" in statuses:
        release_status = "indeterminate"
    elif "warning" in statuses:
        release_status = "warning"
    elif all(status == "pass" for status in statuses):
        release_status = "pass"
    else:
        # Unknown status vocabulary must fail closed rather than becoming pass.
        release_status = "indeterminate"

    critical_blocks = [
        f"{model_id}: critical failure"
        for model_id, gate_status in sorted(report.gate_statuses.items())
        if gate_status == "block"
    ]

    return ExecutiveSummary(
        experiment_id=report.experiment_id,
        project_id=report.project_id,
        release_status=release_status,
        critical_blocks=critical_blocks,
        support_percentage=None,
        uncertainty_percentage=None,
        cost_usd=cost_usd,
        freshness_hours=freshness_hours,
        last_refresh_at=report.generated_at,
        source_snapshot_hash=report.manifest_hash,
    )


def build_analyst_view(report: CanonicalReport, project_id: str) -> AnalystView:
    """Build an analyst view only when canonical and authorized scope match."""
    if not project_id:
        raise ValueError("authorized project scope is required")
    if not report.project_id:
        raise ValueError("Canonical report is missing project scope")
    if report.project_id != project_id:
        raise PermissionError("Canonical report is outside the authorized project scope")

    slices = [
        {
            "model_id": model_id,
            "metrics": sorted(metrics.keys()),
            "gate_status": report.gate_statuses.get(model_id, "unknown"),
        }
        for model_id, metrics in sorted(report.metric_values.items())
    ]
    return AnalystView(
        experiment_id=report.experiment_id,
        project_id=report.project_id,
        slices=slices,
        provenance=[{"artifacts": sorted(report.artifact_hashes)}],
        version_context={
            "manifest": report.manifest_hash,
            "dataset": report.dataset_hash,
        },
    )


def render_redacted_evidence(content: str) -> str:
    """Apply bounded baseline redaction for reviewer queue presentation.

    This helper is intentionally described as pattern masking, not a production
    DLP authority. Raw reveal remains a separate audited workflow.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    redacted = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "[EMAIL REDACTED]",
        content,
    )
    redacted = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE REDACTED]", redacted)
    redacted = re.sub(r"\b\d{8,}\b", "[ID REDACTED]", redacted)
    return redacted


__all__ = [
    "ExecutiveSummary",
    "AnalystView",
    "ReviewerQueueItem",
    "EvidenceRevealRequest",
    "build_executive_summary",
    "build_analyst_view",
    "render_redacted_evidence",
]
