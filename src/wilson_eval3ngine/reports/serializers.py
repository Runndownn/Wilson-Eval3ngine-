"""
Report serializers for TODO 47.

T7.1.3 - JSON, CSV, and Parquet serializers that derive from canonical report.
All serializers produce output that reconciles to the same canonical model.
Security: Prevents CSV formula injection, HTML scripts, and unsafe content.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .models import CanonicalReport


def sanitize_csv_cell(value: Any) -> str:
    """Sanitize a value for CSV output to prevent formula injection."""
    if value is None:
        return ""
    s = str(value)
    dangerous_prefixes = ("=", "+", "-", "@", "\t", "\n", "\r")
    if s.startswith(dangerous_prefixes):
        s = "'" + s
    s = s.replace('"', '""')
    return s


def serialize_to_csv(report: CanonicalReport) -> str:
    """Serialize canonical report to CSV without raw prompts/responses."""
    lines: list[str] = []

    lines.append("section,field,value")
    lines.append(f"experiment,experiment_id,{sanitize_csv_cell(report.experiment_id)}")
    lines.append(f"experiment,project_id,{sanitize_csv_cell(report.project_id)}")
    lines.append(f"experiment,generated_at,{sanitize_csv_cell(report.generated_at)}")
    lines.append(f"experiment,report_hash,{sanitize_csv_cell(report.compute_report_hash())}")
    lines.append(f"experiment,manifest_hash,{sanitize_csv_cell(report.manifest_hash)}")
    lines.append(f"experiment,dataset_hash,{sanitize_csv_cell(report.dataset_hash)}")

    lines.append("")
    lines.append("gates,model,status")
    for model_id, status in sorted(report.gate_statuses.items()):
        lines.append(f"gates,{sanitize_csv_cell(model_id)},{sanitize_csv_cell(status)}")

    lines.append("")
    lines.append("metrics,model,metric_id,value,numerator,denominator")
    for model_id, metrics in sorted(report.metric_values.items()):
        for metric_id, metric in sorted(metrics.items()):
            value = metric.get("value", "undefined")
            numerator = metric.get("numerator", 0)
            denominator = metric.get("denominator", 0)
            lines.append(
                f"metrics,{sanitize_csv_cell(model_id)},"
                f"{sanitize_csv_cell(metric_id)},"
                f"{sanitize_csv_cell(value)},"
                f"{sanitize_csv_cell(numerator)},"
                f"{sanitize_csv_cell(denominator)}"
            )

    lines.append("")
    lines.append("limitations,item")
    for limitation in report.limitations:
        lines.append(f"limitations,{sanitize_csv_cell(limitation)}")

    return "\n".join(lines)


def write_csv_report(report: CanonicalReport, output_path: Path | str) -> Path:
    """Write CSV report to file path."""
    target = Path(output_path)
    target.write_text(serialize_to_csv(report), encoding="utf-8")
    return target


def serialize_to_parquet(report: CanonicalReport) -> bytes:
    """Serialize report metrics to Parquet bytes.

    Parquet support is optional. Missing ``pyarrow`` is an explicit error rather
    than a zero-byte result because an empty byte string can be mistaken for a
    successfully generated evidence artifact.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Parquet export requires the optional 'pyarrow' dependency"
        ) from exc

    report_hash = report.compute_report_hash()
    rows: list[dict[str, Any]] = []
    for model_id, metrics in sorted(report.metric_values.items()):
        for metric_id, metric in sorted(metrics.items()):
            rows.append(
                {
                    "schema_version": report.schema_version,
                    "experiment_id": report.experiment_id,
                    "project_id": report.project_id,
                    "generated_at": report.generated_at,
                    "report_hash": report_hash,
                    "model_id": model_id,
                    "metric_id": metric_id,
                    "value": metric.get("value"),
                    "numerator": metric.get("numerator", 0),
                    "denominator": metric.get("denominator", 0),
                }
            )

    if not rows:
        rows.append(
            {
                "schema_version": report.schema_version,
                "experiment_id": report.experiment_id,
                "project_id": report.project_id,
                "generated_at": report.generated_at,
                "report_hash": report_hash,
                "model_id": None,
                "metric_id": None,
                "value": None,
                "numerator": None,
                "denominator": None,
            }
        )

    table = pa.Table.from_pylist(rows)
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def _json_contains_hash(output: str, expected_hash: str) -> bool:
    """Return whether parsed JSON contains the expected hash as a value."""
    try:
        parsed = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return False

    def contains(value: Any) -> bool:
        if isinstance(value, dict):
            return any(contains(item) for item in value.values())
        if isinstance(value, list):
            return any(contains(item) for item in value)
        return value == expected_hash

    return contains(parsed)


def _csv_contains_hash(output: str, expected_hash: str) -> bool:
    """Return whether parsed CSV contains the expected hash as a cell."""
    try:
        rows = csv.reader(io.StringIO(output))
        return any(expected_hash == cell for row in rows for cell in row)
    except (csv.Error, TypeError):
        return False


def reconcile_report_hash(
    json_output: str,
    csv_output: str,
    html_output: str,
    canonical: CanonicalReport,
) -> dict[str, bool]:
    """Verify each serialization carries the canonical report hash.

    This is a representation-integrity check, not a claim that merely carrying
    a hash proves every field was independently re-derived. A serializer must
    embed the exact canonical hash; malformed or unrelated output fails closed.
    """
    expected_hash = canonical.compute_report_hash()
    return {
        "json": _json_contains_hash(json_output, expected_hash),
        "csv": _csv_contains_hash(csv_output, expected_hash),
        "html": expected_hash in html_output,
    }


__all__ = [
    "sanitize_csv_cell",
    "serialize_to_csv",
    "write_csv_report",
    "serialize_to_parquet",
    "reconcile_report_hash",
]
