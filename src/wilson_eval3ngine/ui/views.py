"""
Persona-specific view models for TODO 48.

T7.1.4 - Deliver safe analyst, executive, and reviewer workflows.
Provides role-appropriate interfaces without exposing restricted evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..reports.models import CanonicalReport


@dataclass(frozen=True, slots=True)
class ExecutiveSummary:
    """Aggregate-only view for executives.

    Security: Contains NO raw evidence, only release status and critical blocks.
    """
    schema_version: str = "we3.executive_summary.v1"
    experiment_id: str = ""
    project_id: str = ""
    release_status: str = "pending"  # pass, block, indeterminate, warning
    critical_blocks: list[str] = field(default_factory=list)
    support_percentage: float = 0.0
    uncertainty_percentage: float = 0.0
    cost_usd: float = 0.0
    freshness_hours: float = 0.0
    last_refresh_at: str = ""
    source_snapshot_hash: str = ""


@dataclass(frozen=True, slots=True)
class AnalystView:
    """Drill-down view for analysts with lineage.

    Security: Full lineage within authorized project scope.
    No cross-project data exposure.
    """
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
    freshness_state: str = "fresh"  # fresh, stale, invalid


@dataclass(frozen=True, slots=True)
class ReviewerQueueItem:
    """Redacted evidence item for reviewer queue.

    Security: Evidence is redacted by default.
    Raw reveal requires explicit approval flow.
    """
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
    """Request to reveal restricted evidence.

    Security: Audit requirement for raw evidence access.
    """
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
    """Build aggregate summary from canonical report.

    Implements TODO 48 requirement: Executives see only aggregates.
    """
    if not report.gate_statuses:
        status = "indeterminate"
    elif any(s == "block" for s in report.gate_statuses.values()):
        status = "block"
    elif any(s == "indeterminate" for s in report.gate_statuses.values()):
        status = "indeterminate"
    elif any(s == "warning" for s in report.gate_statuses.values()):
        status = "warning"
    else:
        status = "pass"

    blocks = []
    for model_id, status in report.gate_statuses.items():
        if status == "block":
            blocks.append(f"{model_id}: critical failure")

    return ExecutiveSummary(
        experiment_id=report.experiment_id,
        project_id=report.project_id,
        release_status=status,
        critical_blocks=blocks,
        support_percentage=100.0,  # Provisional: canonical report lacks an aggregate support contract.
        uncertainty_percentage=0.0,  # Provisional: canonical report lacks an aggregate uncertainty contract.
        cost_usd=cost_usd,
        freshness_hours=freshness_hours,
        last_refresh_at=report.generated_at,
        source_snapshot_hash=report.manifest_hash,
    )


def build_analyst_view(
    report: CanonicalReport,
    project_id: str,
) -> AnalystView:
    """Build an analyst drill-down view within one authorized project.

    The caller-supplied project ID is treated as the authorization scope. A
    canonical report carrying a different project ID is rejected before any
    metrics, artifact hashes, or other lineage is copied into the view. Reports
    without a project ID are also rejected because an unscoped report cannot be
    safely exposed through a project-scoped analyst view.
    """
    if not report.project_id:
        raise ValueError("Canonical report is missing project scope")
    if report.project_id != project_id:
        raise PermissionError("Canonical report is outside the authorized project scope")

    slices = []
    for model_id, metrics in report.metric_values.items():
        slice_data = {
            "model_id": model_id,
            "metrics": list(metrics.keys()),
            "gate_status": report.gate_statuses.get(model_id, "unknown"),
        }
        slices.append(slice_data)

    return AnalystView(
        experiment_id=report.experiment_id,
        project_id=report.project_id,
        slices=slices,
        cases=[],  # Populated only when authorized evidence-store integration supplies them.
        attempts=[],
        grades=[],
        reviews=[],
        provenance=[{"artifacts": report.artifact_hashes}],
        version_context={
            "manifest": report.manifest_hash,
            "dataset": report.dataset_hash,
        },
    )


def render_redacted_evidence(content: str) -> str:
    """Render evidence in redacted form for reviewer queue.

    Security: PII/restricted content is masked. This helper is a baseline
    pattern redactor, not a complete production DLP policy.
    """
    import re

    content = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL REDACTED]", content)
    content = re.sub(r"\b\d{8,}\b", "[ID REDACTED]", content)
    content = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE REDACTED]", content)
    return content


__all__ = [
    "ExecutiveSummary",
    "AnalystView",
    "ReviewerQueueItem",
    "EvidenceRevealRequest",
    "build_executive_summary",
    "build_analyst_view",
    "render_redacted_evidence",
]
