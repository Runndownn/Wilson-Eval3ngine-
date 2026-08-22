"""Unit tests for TODO 47 report models and serializers."""

import json

from wilson_eval3ngine.reports.models import CanonicalReport, ExportRequest, ExportState
from wilson_eval3ngine.reports.serializers import (
    sanitize_csv_cell,
    serialize_to_csv,
    reconcile_report_hash,
)


class TestCanonicalReport:
    """Tests for canonical report model."""

    def test_canonical_report_deterministic_hash(self):
        """Report hash is deterministic for same content."""
        report = CanonicalReport(
            experiment_id="exp_test",
            project_id="proj_1",
            generated_at="2024-01-01T00:00:00Z",
            manifest_hash="abc123",
            dataset_hash="def456",
            metric_values={"model_a": {"metric_x": {"value": 0.5}}},
            gate_statuses={"model_a": "pass"},
        )
        hash1 = report.compute_report_hash()

        report2 = CanonicalReport(
            experiment_id="exp_test",
            project_id="proj_1",
            generated_at="2024-01-01T00:00:00Z",
            manifest_hash="abc123",
            dataset_hash="def456",
            metric_values={"model_a": {"metric_x": {"value": 0.5}}},
            gate_statuses={"model_a": "pass"},
        )
        hash2 = report2.compute_report_hash()
        assert hash1 == hash2

    def test_canonical_report_sorted_output(self):
        """Report output is deterministically ordered."""
        report = CanonicalReport(
            experiment_id="exp_test",
            metric_values={
                "model_b": {"m2": {"value": 1.0}},
                "model_a": {"m1": {"value": 0.5}},
            },
            gate_statuses={
                "model_b": "pass",
                "model_a": "warning",
            },
        )
        output = report.to_dict()
        assert list(output["metric_values"].keys()) == ["model_a", "model_b"]
        assert list(output["gate_statuses"].keys()) == ["model_a", "model_b"]


class TestExportState:
    """Tests for export state enum."""

    def test_export_states_exist(self):
        """All required export states are defined."""
        assert ExportState.REQUESTED.value == "requested"
        assert ExportState.AUTHORIZED.value == "authorized"
        assert ExportState.BUILDING.value == "building"
        assert ExportState.READY.value == "ready"
        assert ExportState.FAILED.value == "failed"
        assert ExportState.EXPIRED.value == "expired"


class TestExportRequest:
    """Tests for export request model."""

    def test_export_request_default_state(self):
        """Export request defaults to REQUESTED state."""
        req = ExportRequest(export_id="exp_123", project_id="proj_1")
        assert req.state == ExportState.REQUESTED

    def test_export_request_to_dict(self):
        """Export request serialization includes schema_version."""
        req = ExportRequest(
            export_id="exp_123",
            export_type="dossier",
            resource_id="res_456",
            project_id="proj_1",
        )
        output = req.to_dict()
        assert output["schema_version"] == "we3.export_request.v1"
        assert output["state"] == "requested"


class TestCsvSanitization:
    """Tests for CSV formula injection prevention."""

    def test_sanitize_normal_value(self):
        assert sanitize_csv_cell("hello") == "hello"
        assert sanitize_csv_cell(42) == "42"
        assert sanitize_csv_cell(3.14) == "3.14"

    def test_sanitize_formula_prefix(self):
        assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        assert sanitize_csv_cell("+cmd") == "'+cmd"
        assert sanitize_csv_cell("-sub") == "'-sub"
        assert sanitize_csv_cell("@email") == "'@email"

    def test_sanitize_special_chars(self):
        assert sanitize_csv_cell("\tcmd") == "'\tcmd"

    def test_sanitize_quotes(self):
        assert sanitize_csv_cell('say "hi"') == 'say ""hi""'


class TestCsvSerialization:
    """Tests for CSV serialization."""

    def test_serialize_to_csv_structure(self):
        report = CanonicalReport(
            experiment_id="exp_123",
            project_id="proj_1",
            gate_statuses={"model_a": "pass", "model_b": "warning"},
            metric_values={
                "model_a": {
                    "WE3-HELP-FRR": {
                        "value": 0.05,
                        "numerator": 25,
                        "denominator": 500,
                    }
                }
            },
        )
        csv_output = serialize_to_csv(report)
        lines = csv_output.split("\n")
        assert any("experiment,experiment_id" in line for line in lines)
        assert any("gates,model_a" in line for line in lines)
        assert any("metrics,model_a" in line for line in lines)

    def test_serialize_csv_no_raw_evidence(self):
        report = CanonicalReport(
            experiment_id="exp_123",
            gate_statuses={"model_a": "pass"},
        )
        csv_output = serialize_to_csv(report)
        assert "prompt" not in csv_output.lower()
        assert "response" not in csv_output.lower()
        assert "raw" not in csv_output.lower()


class TestReconciliation:
    """Tests for cross-format reconciliation."""

    def test_reconcile_report_hash_accepts_embedded_canonical_hash(self):
        report = CanonicalReport(
            experiment_id="exp_123",
            gate_statuses={"model_a": "pass"},
        )
        report_hash = report.compute_report_hash()
        result = reconcile_report_hash(
            json_output=json.dumps({"report_hash": report_hash}),
            csv_output=f"section,field,value\nexperiment,report_hash,{report_hash}",
            html_output=f'<html><meta name="we3-report-hash" content="{report_hash}"></html>',
            canonical=report,
        )
        assert result == {"json": True, "csv": True, "html": True}

    def test_reconcile_report_hash_rejects_unrelated_outputs(self):
        report = CanonicalReport(
            experiment_id="exp_123",
            gate_statuses={"model_a": "pass"},
        )
        result = reconcile_report_hash(
            json_output="{}",
            csv_output="section,field,value",
            html_output="<html></html>",
            canonical=report,
        )
        assert result == {"json": False, "csv": False, "html": False}

    def test_reconcile_report_hash_detects_mixed_format_mismatch(self):
        report = CanonicalReport(experiment_id="exp_123")
        report_hash = report.compute_report_hash()
        result = reconcile_report_hash(
            json_output=json.dumps({"report_hash": report_hash}),
            csv_output="section,field,value\nexperiment,report_hash,wrong-hash",
            html_output=f"<html>{report_hash}</html>",
            canonical=report,
        )
        assert result == {"json": True, "csv": False, "html": True}
