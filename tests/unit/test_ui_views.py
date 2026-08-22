"""Unit tests for TODO 48 persona-specific views."""

import pytest

from wilson_eval3ngine.reports.models import CanonicalReport
from wilson_eval3ngine.ui.views import (
    build_executive_summary,
    build_analyst_view,
    render_redacted_evidence,
)


class TestExecutiveSummary:
    """Tests for executive view model."""

    def test_executive_summary_no_raw_evidence(self):
        """Executive summary contains no raw evidence."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            gate_statuses={"model_a": "pass", "model_b": "block"},
        )
        summary = build_executive_summary(report)
        assert summary.schema_version == "we3.executive_summary.v1"
        summary_slots = {f.name for f in summary.__dataclass_fields__.values()}
        assert "redacted_evidence" not in summary_slots
        assert "raw_evidence" not in summary_slots

    def test_executive_summary_aggregates_only(self):
        """Executive summary shows aggregate status only."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            gate_statuses={"model_a": "pass", "model_b": "warning"},
        )
        summary = build_executive_summary(report, cost_usd=5.50)
        assert summary.release_status == "warning"
        assert summary.cost_usd == 5.50
        assert summary.critical_blocks == []

    def test_executive_summary_critical_blocks(self):
        """Critical blocks are included in summary."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            gate_statuses={"model_a": "pass", "model_b": "block"},
        )
        summary = build_executive_summary(report)
        assert summary.release_status == "block"
        assert len(summary.critical_blocks) == 1


class TestAnalystView:
    """Tests for analyst drill-down view."""

    def test_analyst_view_lineage(self):
        """Analyst view preserves lineage context."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            manifest_hash="hash_manifest",
            dataset_hash="hash_dataset",
            metric_values={"model_a": {"m1": {"value": 0.5}}},
            gate_statuses={"model_a": "pass"},
        )
        view = build_analyst_view(report, "proj_1")
        assert view.version_context["manifest"] == "hash_manifest"
        assert view.version_context["dataset"] == "hash_dataset"
        assert len(view.slices) == 1

    def test_analyst_view_no_cross_project(self):
        """Analyst view is scoped to the canonical report's project."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
        )
        view = build_analyst_view(report, "proj_1")
        assert view.project_id == "proj_1"

    def test_analyst_view_rejects_cross_project_report(self):
        """A caller cannot relabel another project's report as authorized."""
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            artifact_hashes=["sensitive-artifact-hash"],
        )
        with pytest.raises(PermissionError, match="outside the authorized project scope"):
            build_analyst_view(report, "proj_2")

    def test_analyst_view_rejects_unscoped_report(self):
        """Unscoped reports cannot be exposed through a scoped analyst view."""
        report = CanonicalReport(experiment_id="exp_123")
        with pytest.raises(ValueError, match="missing project scope"):
            build_analyst_view(report, "proj_1")


class TestRedaction:
    """Tests for evidence redaction."""

    def test_redact_email_addresses(self):
        """Email addresses are redacted."""
        content = "Contact us at admin@example.com for details"
        redacted = render_redacted_evidence(content)
        assert "[EMAIL REDACTED]" in redacted
        assert "admin@example.com" not in redacted

    def test_redact_long_ids(self):
        """Long numeric sequences are redacted."""
        content = "Case ID: 12345678 and reference 87654321"
        redacted = render_redacted_evidence(content)
        assert "[ID REDACTED]" in redacted

    def test_redact_phone_numbers(self):
        """Phone numbers are redacted."""
        content = "Call 555-123-4567 for assistance"
        redacted = render_redacted_evidence(content)
        assert "[PHONE REDACTED]" in redacted
