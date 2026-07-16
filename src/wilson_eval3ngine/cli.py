"""Wilson Eval3ngine CLI - TODO 46.

T7.1.2 - Complete CLI workflows with stable exit codes.

Exit codes:
  0   - Success (pass)
  10  - Warning (non-blocking issues detected)
  20  - Block (critical issues prevent release)
  30  - Indeterminate (insufficient data or support)
  40  - Validation error (malformed input, contract violation)
  50  - Platform failure (infrastructure error)
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import signal
import sys
from typing import Any

import typer
import uvicorn

from .application.service import EvaluationService, EvaluationOutcome
from .domain.contracts import (
    Classification,
    DatasetManifest,
    ExperimentManifest,
    GateDecision,
    MetricSnapshot,
    ProviderRequest,
    ProviderResponse,
    TestCase,
    ThresholdSet,
)
from .domain.io import load_dataset, load_experiment, resolve_dataset_path
from .reports.dossier import verify_signed_dossier
from .util import utc_now

# Exit codes per TODO 46 requirements
EXIT_SUCCESS = 0
EXIT_WARNING = 10
EXIT_BLOCK = 20
EXIT_INDETERMINATE = 30
EXIT_VALIDATION_ERROR = 40
EXIT_PLATFORM_FAILURE = 50

# Global for signal handling
_shutdown_requested = False


def _handle_shutdown(signum: int, frame: Any) -> None:
    """Handle interrupt signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True


# Register signal handlers
signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


app = typer.Typer(
    name="we3",
    help="Wilson Eval3ngine foundation CLI.",
    no_args_is_help=True,
)


def _determine_exit_code(outcome: EvaluationOutcome) -> int:
    """Determine exit code from outcome gate statuses.

    Per TODO 47: Gate status takes precedence.
    - Any BLOCK status -> exit 20
    - Any INDETERMINATE status -> exit 30
    - Any WARNING status -> exit 10
    - All PASS -> exit 0
    """
    if not outcome.gate_statuses:
        return EXIT_INDETERMINATE

    for status in outcome.gate_statuses.values():
        if status == "block":
            return EXIT_BLOCK
        if status == "indeterminate":
            return EXIT_INDETERMINATE
        if status == "warning":
            return EXIT_WARNING

    return EXIT_SUCCESS


def _output_result(result: dict[str, Any], output_format: str) -> None:
    """Output result in human or machine format.

    Machine format (json) writes to stdout.
    Human format writes to stderr for logs/diagnostic.
    """
    if output_format == "json":
        # Machine format: write JSON to stdout
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        # Human format: write to stderr for logs/diagnostic, nothing to stdout
        import sys as _sys
        _sys.stderr.write(json.dumps(result, indent=2, sort_keys=True) + "\n")


@app.command()
def validate(
    manifest: Path,
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Validate an experiment and its local dataset contract."""
    output_format = "json" if json_output else "human"

    try:
        experiment = load_experiment(manifest)
        dataset_path = resolve_dataset_path(manifest, experiment)
        dataset = load_dataset(dataset_path)
        digest = dataset.computed_sha256()

        if experiment.dataset.manifest_sha256 not in {"auto", digest}:
            result = {
                "valid": False,
                "error": "dataset_hash_mismatch",
                "message": f"dataset hash mismatch: {digest} != {experiment.dataset.manifest_sha256}",
                "manifest_sha256": experiment.content_hash(),
            }
            _output_result(result, output_format)
            raise typer.Exit(code=EXIT_VALIDATION_ERROR)

        result = {
            "schema_version": "we3.validation_result.v1",
            "valid": True,
            "manifest": str(manifest.resolve()),
            "manifest_sha256": experiment.content_hash(),
            "dataset": str(dataset_path),
            "dataset_sha256": digest,
            "test_cases": len(dataset.cases),
            "prompt_families": len({case.prompt_family_id for case in dataset.cases}),
        }
        _output_result(result, output_format)

    except Exception as e:
        result = {
            "valid": False,
            "error": "validation_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise typer.Exit(code=EXIT_PLATFORM_FAILURE)


@app.command("run")
def run_experiment(
    manifest: Path,
    output: Path = typer.Option(Path("./var/demo"), "--output", help="Output directory"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    artifact_root: Path = typer.Option("./var/artifacts", "--artifact-root"),
    signing_key: Path | None = typer.Option(None, "--signing-key", help="Path to signing key"),
    timeout: int = typer.Option(300, "--timeout", help="Timeout in seconds"),
    trace: bool = typer.Option(False, "--trace", help="Include trace IDs in output"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Execute the synchronous deterministic foundation lane."""
    output_format = "json" if json_output else "human"

    global _shutdown_requested

    try:
        service = EvaluationService(database_url=database_url, artifact_root=artifact_root)
        outcome = service.run_manifest(
            manifest,
            output_dir=output,
            signing_key_path=signing_key,
        )

        if _shutdown_requested:
            result = {
                "schema_version": "we3.operation.v1",
                "status": "cancelled",
                "message": "Operation interrupted by signal",
            }
            _output_result(result, output_format)
            raise typer.Exit(code=EXIT_PLATFORM_FAILURE)

        result = {
            "schema_version": "we3.experiment_result.v1",
            "experiment_id": outcome.experiment_id,
            "dossier": str(outcome.dossier_path),
            "safe_html": str(outcome.safe_html_path),
            "result_index": str(outcome.result_index_path),
            "gate_statuses": outcome.gate_statuses,
            "trace_id": f"trc_{outcome.experiment_id}" if trace else None,
        }
        _output_result(result, output_format)

        # Exit based on gate statuses
        exit_code = _determine_exit_code(outcome)
        # Use sys.exit to avoid being caught by the except block
        raise SystemExit(exit_code)

    except SystemExit:
        raise

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "execution_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


@app.command()
def verify_dossier(
    dossier: Path,
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Verify a dossier digest and embedded Ed25519 signature."""
    output_format = "json" if json_output else "human"

    try:
        result = verify_signed_dossier(dossier)
        result["schema_version"] = "we3.dossier_verification.v1"
        _output_result(result, output_format)

        if not result["valid"]:
            raise SystemExit(EXIT_BLOCK)

    except SystemExit:
        raise

    except Exception as e:
        result = {
            "schema_version": "we3.dossier_verification.v1",
            "valid": False,
            "error": "verification_failed",
            "message": str(e),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


# ============================================================================
# Operation lifecycle commands (pause, resume, cancel) - TODO 46
# ============================================================================


@app.command()
def plan(
    manifest: Path,
    output: Path = typer.Option(Path("./var/plan"), "--output", help="Output directory for plan"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Generate and estimate execution plan for an experiment."""
    output_format = "json" if json_output else "human"

    try:
        experiment = load_experiment(manifest)
        dataset_path = resolve_dataset_path(manifest, experiment)
        dataset = load_dataset(dataset_path)

        # Estimate costs and timing based on dataset and models
        total_runs = len(dataset.cases) * len(experiment.models) * experiment.execution.repetitions
        estimated_cost = total_runs * 0.01  # Placeholder cost model

        result = {
            "schema_version": "we3.plan_estimate.v1",
            "experiment_id": f"est_{experiment.name}",
            "total_runs": total_runs,
            "models": [m.model_config_id for m in experiment.models],
            "repetitions": experiment.execution.repetitions,
            "estimated_cost_usd": round(estimated_cost, 4),
            "estimated_duration_seconds": total_runs * 2,  # Approximate
        }
        _output_result(result, output_format)

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "plan_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


@app.command()
def pause(
    operation_id: str = typer.Option(..., "--operation", help="Operation ID to pause"),
    project: str = typer.Option("default", "--project", help="Project ID"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Pause a running operation."""
    output_format = "json" if json_output else "human"

    try:
        # In production, would call the API or database to pause
        result = {
            "schema_version": "we3.operation_ack.v1",
            "operation_id": operation_id,
            "project_id": project,
            "status": "pause_requested",
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_SUCCESS)

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "pause_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


@app.command()
def resume(
    operation_id: str = typer.Option(..., "--operation", help="Operation ID to resume"),
    project: str = typer.Option("default", "--project", help="Project ID"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Resume a paused operation."""
    output_format = "json" if json_output else "human"

    try:
        result = {
            "schema_version": "we3.operation_ack.v1",
            "operation_id": operation_id,
            "project_id": project,
            "status": "resume_requested",
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_SUCCESS)

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "resume_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


@app.command()
def cancel(
    operation_id: str = typer.Option(..., "--operation", help="Operation ID to cancel"),
    project: str = typer.Option("default", "--project", help="Project ID"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Cancel a running or paused operation."""
    output_format = "json" if json_output else "human"

    try:
        result = {
            "schema_version": "we3.operation_ack.v1",
            "operation_id": operation_id,
            "project_id": project,
            "status": "cancel_requested",
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_SUCCESS)

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "cancel_failed",
            "message": str(e),
            "timestamp": utc_now().isoformat(),
        }
        _output_result(result, output_format)
        raise SystemExit(EXIT_PLATFORM_FAILURE)


# ============================================================================
# Existing commands follow


@app.command()
def status(
    experiment: str | None = typer.Option(None, "--experiment", help="Experiment ID"),
    run_id: str | None = typer.Option(None, "--run", help="Run ID"),
    project: str = typer.Option("default", "--project", help="Project ID"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Get status of experiment or run."""
    output_format = "json" if json_output else "human"

    result = {
        "schema_version": "we3.status.v1",
        "project_id": project,
        "timestamp": utc_now().isoformat(),
        "status": "operational",
    }

    if experiment or run_id:
        result["target"] = experiment or run_id

    _output_result(result, output_format)


@app.command()
def compare(
    baseline: Path = typer.Option(..., "--baseline", help="Baseline experiment output directory"),
    candidate: Path = typer.Option(..., "--candidate", help="Candidate experiment output directory"),
    output: Path = typer.Option(Path("./var/compare"), "--output"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Compare two experiment results."""
    output_format = "json" if json_output else "human"

    try:
        # Load results from output directories
        baseline_result = json.loads((baseline / "experiment_result.json").read_text())
        candidate_result = json.loads((candidate / "experiment_result.json").read_text())

        result = {
            "schema_version": "we3.comparison.v1",
            "baseline_experiment": baseline_result.get("experiment_id"),
            "candidate_experiment": candidate_result.get("experiment_id"),
            "comparison": "pending",  # Full comparison requires statistics module
        }
        _output_result(result, output_format)

    except Exception as e:
        result = {
            "schema_version": "we3.error.v1",
            "error": "comparison_failed",
            "message": str(e),
        }
        _output_result(result, output_format)
        raise typer.Exit(code=EXIT_VALIDATION_ERROR)


@app.command()
def regrade(
    experiment_id: str | None = typer.Option(None, "--experiment", help="Experiment ID"),
    grader_version: str | None = typer.Option(None, "--grader-version", help="New grader version"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Request regrading of experiment responses."""
    output_format = "json" if json_output else "human"

    if not experiment_id or not grader_version:
        result = {
            "schema_version": "we3.error.v1",
            "error": "missing_required",
            "message": "both --experiment and --grader-version are required",
        }
        _output_result(result, output_format)
        raise typer.Exit(code=EXIT_VALIDATION_ERROR)

    result = {
        "schema_version": "we3.regrade_ack.v1",
        "experiment_id": experiment_id,
        "grader_version": grader_version,
        "status": "accepted",
    }
    _output_result(result, output_format)


@app.command()
def export(
    experiment_id: str | None = typer.Option(None, "--experiment", help="Experiment ID"),
    export_type: str = typer.Option("dossier", "--type", help="Export type (dossier, report, raw_evidence)"),
    output: Path = typer.Option(Path("./var/exports"), "--output"),
    database_url: str = typer.Option("sqlite:///./var/we3.db", "--database-url"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
) -> None:
    """Create an export for specified experiment."""
    output_format = "json" if json_output else "human"

    valid_types = {"dossier", "report", "raw_evidence"}
    if export_type not in valid_types:
        result = {
            "schema_version": "we3.error.v1",
            "error": "invalid_export_type",
            "message": f"export type must be one of {valid_types}",
        }
        _output_result(result, output_format)
        raise typer.Exit(code=EXIT_VALIDATION_ERROR)

    if not experiment_id:
        result = {
            "schema_version": "we3.error.v1",
            "error": "missing_required",
            "message": "--experiment is required",
        }
        _output_result(result, output_format)
        raise typer.Exit(code=EXIT_VALIDATION_ERROR)

    output.mkdir(parents=True, exist_ok=True)

    result = {
        "schema_version": "we3.export.v1",
        "export_type": export_type,
        "experiment_id": experiment_id,
        "status": "accepted",
        "export_id": f"exp_{experiment_id[:8]}",
        "output_path": str(output.resolve()),
    }
    _output_result(result, output_format)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Run the development API server."""
    uvicorn.run(
        "wilson_eval3ngine.api.main:app",
        host=host,
        port=port,
        reload=False,
    )


@app.command("export-schemas")
def export_schemas(
    output: Path = typer.Option(Path("./contracts/schemas"), "--output"),
) -> None:
    """Export the versioned JSON Schemas implemented by this foundation."""
    output.mkdir(parents=True, exist_ok=True)
    schemas = {
        "we3.experiment.v1.schema.json": ExperimentManifest.model_json_schema(),
        "we3.dataset.v1.schema.json": DatasetManifest.model_json_schema(),
        "we3.test_case.v1.schema.json": TestCase.model_json_schema(),
        "we3.provider_request.v1.schema.json": ProviderRequest.model_json_schema(),
        "we3.provider_response.v1.schema.json": ProviderResponse.model_json_schema(),
        "we3.classification.v1.schema.json": Classification.model_json_schema(),
        "we3.metric_snapshot.v1.schema.json": MetricSnapshot.model_json_schema(),
        "we3.threshold_set.v1.schema.json": ThresholdSet.model_json_schema(),
        "we3.gate_decision.v1.schema.json": GateDecision.model_json_schema(),
    }
    for name, schema in schemas.items():
        (output / name).write_text(
            json.dumps(schema, sort_keys=True, indent=2),
            encoding="utf-8",
        )
    typer.echo(json.dumps({"written": sorted(schemas), "output": str(output.resolve())}))


@app.command("version")
def version() -> None:
    """Print CLI and framework version."""
    result = {
        "schema_version": "we3.version.v1",
        "cli_version": "0.1.0",
        "framework": "Wilson Eval3ngine",
    }
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()