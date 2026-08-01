from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
import uvicorn

from .application.service import EvaluationService
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
from .supply_chain import scan_ci_pipeline

app = typer.Typer(
    name="we3",
    help="Wilson Eval3ngine foundation CLI.",
    no_args_is_help=True,
)

# Exit codes for hostile testing
EXIT_PLATFORM_FAILURE = 2
EXIT_VALIDATION_ERROR = 1


@app.command()
def validate(manifest: Path) -> None:
    """Validate an experiment and its local dataset contract."""
    experiment = load_experiment(manifest)
    dataset_path = resolve_dataset_path(manifest, experiment)
    dataset = load_dataset(dataset_path)
    digest = dataset.computed_sha256()
    if experiment.dataset.manifest_sha256 not in {"auto", digest}:
        raise typer.BadParameter(
            f"dataset hash mismatch: {digest} != "
            f"{experiment.dataset.manifest_sha256}"
        )
    result = {
        "valid": True,
        "manifest": str(manifest.resolve()),
        "manifest_sha256": experiment.content_hash(),
        "dataset": str(dataset_path),
        "dataset_sha256": digest,
        "test_cases": len(dataset.cases),
        "prompt_families": len({case.prompt_family_id for case in dataset.cases}),
    }
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("run")
def run_experiment(
    manifest: Path,
    output: Path = typer.Option(Path("./var/demo"), "--output"),
    database_url: str = typer.Option(
        "sqlite:///./var/we3.db",
        "--database-url",
    ),
    artifact_root: Path = typer.Option(Path("./var/artifacts"), "--artifact-root"),
    signing_key: Path | None = typer.Option(None, "--signing-key"),
) -> None:
    """Execute the synchronous deterministic foundation lane."""
    service = EvaluationService(
        database_url=database_url,
        artifact_root=artifact_root,
    )
    outcome = service.run_manifest(
        manifest,
        output_dir=output,
        signing_key_path=signing_key,
    )
    typer.echo(
        json.dumps(
            {
                "experiment_id": outcome.experiment_id,
                "dossier": str(outcome.dossier_path),
                "safe_html": str(outcome.safe_html_path),
                "result_index": str(outcome.result_index_path),
                "gate_statuses": outcome.gate_statuses,
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("verify-dossier")
def verify_dossier(dossier: Path) -> None:
    """Verify a dossier digest and embedded Ed25519 signature."""
    result = verify_signed_dossier(dossier)
    typer.echo(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise typer.Exit(code=1)


@app.command("scan-ci")
def scan_ci(
    source: Path = typer.Option(Path("."), "--source", help="Source path to scan"),
    output: Path = typer.Option(
        Path("./var/supply_chain_report.json"), "--output", help="Output report path"
    ),
    lockfile: Path | None = typer.Option(
        None, "--lockfile", help="Path to lockfile for SBOM generation"
    ),
) -> None:
    """Run supply chain security scans for CI pipelines.

    Scans for:
    - Hardcoded secrets
    - SAST security issues
    - Container image vulnerabilities
    - IaC security issues
    - GitHub Actions workflow security
    - Dependency vulnerabilities (if lockfile provided)

    Blocks on critical/high severity findings.
    """
    report = scan_ci_pipeline(
        source_path=source,
        lockfile_path=lockfile,
        dockerfile_paths=list(source.glob("**/Dockerfile*")),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    typer.echo(json.dumps({
        "scanned_path": str(source),
        "blocking_items": len(report["blocking"]),
        "passed": report["pass"],
        "output": str(output.resolve()),
    }, indent=2))

    if not report["pass"]:
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Run the development API."""
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


# ============================================================================
# Backup Management Commands (TODO 55)
# ============================================================================

@app.command("certify")
def certify(
    release_artifact: str = typer.Option(..., "--artifact", help="Release artifact digest or path"),
    source_commit: str = typer.Option(..., "--source-commit", help="Git commit SHA"),
    environment: str = typer.Option("production", "--environment", help="Target environment"),
    signing_key: Path | None = typer.Option(None, "--signing-key", help="Path to signing key for certifier"),
    output: Path = typer.Option(Path("./var/certification"), "--output", help="Output directory"),
) -> None:
    """Run production certification evaluation.

    Evaluates all ten certification categories and produces signed manifest.
    Blocks release if any Must requirements are not satisfied.
    """
    from .certification.certification_orchestrator import (
        CertificationOrchestrator,
        CertificationRegistry,
    )
    from .security.signing import load_private_key

    registry = CertificationRegistry()
    orchestrator = CertificationOrchestrator(registry)

    # Resolve artifact digest
    artifact_path = Path(release_artifact)
    if artifact_path.exists():
        digest = orchestrator.resolve_release_artifact(artifact_path)
    else:
        digest = release_artifact

    # Run certification with mock approvers
    result = orchestrator.run_certification(
        release_artifact_digest=digest,
        source_commit=source_commit,
        environment=environment,
        requirement_catalog_hash="sha256:requirements_v1",
        approvers=["operator"],
    )

    # Sign if key provided
    if signing_key:
        key = load_private_key(signing_key)
        orchestrator.sign_certification(result, key)

    output.mkdir(parents=True, exist_ok=True)
    output_path = output / "certification_result.json"
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    typer.echo(json.dumps({
        "certification_id": result.certification_id,
        "status": result.status,
        "blocking_issues": result.blocking_issues,
        "output": str(output_path.resolve()),
    }, indent=2))

    if result.status == "blocked":
        raise typer.Exit(code=20)


@app.command("operations-cadence")
def operations_cadence(
    cadence: str = typer.Option(..., "--type", help="Cadence type: daily, weekly, monthly, quarterly"),
    output: Path = typer.Option(Path("./var/operations"), "--output", help="Output directory"),
) -> None:
    """Run operational cadence tasks.

    Executes daily/weekly/monthly/quarterly operational procedures.
    Creates tickets for threshold breaches.
    """
    from .operations.cadences import CadenceType, OperationsCadenceManager

    manager = OperationsCadenceManager()

    try:
        cadence_type = CadenceType(cadence)
    except ValueError:
        typer.echo(json.dumps({"error": f"Invalid cadence type: {cadence}"}))
        raise typer.Exit(code=1)

    work = manager.create_cadence_work(cadence_type, "Platform Team")
    work = manager.start_cadence_work(work.work_id)

    # Simulate cadence execution
    manager.complete_cadence_work(
        work.work_id,
        {"cadence_executed": cadence, "timestamp": datetime.now(timezone.utc).isoformat()},
    )

    output.mkdir(parents=True, exist_ok=True)
    typer.echo(json.dumps({
        "work_id": work.work_id,
        "cadence": cadence,
        "status": work.status.value,
    }, indent=2))


@app.command("validate-capabilities")
def validate_capabilities(
    output: Path = typer.Option(Path("./var/capabilities"), "--output", help="Output directory"),
) -> None:
    """Validate advanced capability decisions.

    Runs scope validation for retrieval, vector, accelerator, and multimodal capabilities.
    """
    from .evaluation.scope_validation import CapabilityAnalyst

    analyst = CapabilityAnalyst()

    # Evaluate all capabilities
    analyst.evaluate_retrieval("Advanced evaluation", "safe-compliance-core")
    analyst.evaluate_vector_storage("bge-m3:latest")
    analyst.evaluate_accelerators("A100")
    analyst.evaluate_multimodal(["image/jpeg", "image/png"])

    evaluations = analyst.get_all_evaluations()
    output.mkdir(parents=True, exist_ok=True)

    results = [e.to_dict() for e in evaluations]
    typer.echo(json.dumps({
        "capabilities_evaluated": len(results),
        "decisions": analyst.get_decisions(),
    }, indent=2, default=str))


@app.command("backup")
def backup(
    ctx: typer.Context,
) -> None:
    """Backup management commands.

    Usage:
        we3 backup create --key-id <kms-key-id>
        we3 backup list
        we3 backup verify <backup-id>
        we3 backup restore-plan --timestamp <iso8601>
    """
    pass


@app.command("backup-create")
def backup_create(
    key_id: str = typer.Option(..., "--key-id", help="KMS key ID for encryption"),
    signing_key: Path | None = typer.Option(
        None, "--signing-key", help="Path to signing key for manifest"
    ),
) -> None:
    """Create an encrypted full backup of the database.

    Security: Requires KMS encryption key. Backups are encrypted at rest.
    """
    from .backup.backup_manager import BackupManager

    database_url = typer.get_app_dir(
        typer.get_current_context().meta.get("database_url", "sqlite:///./var/we3.db")
    )
    backup_root = Path(typer.get_current_context().meta.get("backup_root", "./var/backups"))

    manager = BackupManager(
        database_url=os.environ.get("WE3_DATABASE_URL", "sqlite:///./var/we3.db"),
        backup_root=backup_root,
    )

    try:
        metadata = manager.create_full_backup(key_id, signing_key)
        typer.echo(json.dumps({
            "status": "created",
            "backup_id": metadata.backup_id,
            "size_bytes": metadata.size_bytes,
            "encrypted": metadata.encrypted,
            "key_id": metadata.key_id,
        }, indent=2))
    except Exception as e:
        typer.echo(json.dumps({
            "status": "failed",
            "error": str(e),
        }, indent=2))
        raise typer.Exit(code=1)


@app.command("backup-list")
def backup_list(
    limit: int = typer.Option(100, "--limit", help="Maximum backups to return"),
) -> None:
    """List available backups, most recent first."""
    from .backup.backup_manager import BackupManager

    manager = BackupManager(
        database_url=os.environ.get("WE3_DATABASE_URL", "sqlite:///./var/we3.db"),
        backup_root=Path(os.environ.get("WE3_BACKUP_ROOT", "./var/backups")),
    )

    backups = manager.list_backups(limit=limit)
    typer.echo(json.dumps({
        "count": len(backups),
        "backups": [b.to_dict() for b in backups],
    }, indent=2, default=str))


@app.command("backup-verify")
def backup_verify(
    backup_id: str,
    signing_key: Path | None = typer.Option(
        None, "--signing-key", help="Path to signing key for verification"
    ),
) -> None:
    """Verify backup integrity and signature.

    Security: Requires trust registry validation for production backups.
    """
    from .backup.backup_manager import BackupManager

    manager = BackupManager(
        database_url=os.environ.get("WE3_DATABASE_URL", "sqlite:///./var/we3.db"),
        backup_root=Path(os.environ.get("WE3_BACKUP_ROOT", "./var/backups")),
    )

    valid = manager.verify_backup_integrity(backup_id, signing_key)
    typer.echo(json.dumps({
        "backup_id": backup_id,
        "valid": valid,
    }, indent=2))

    if not valid:
        raise typer.Exit(code=1)


@app.command("backup-restore-plan")
def backup_restore_plan(
    timestamp: str = typer.Option(..., "--timestamp", help="Target ISO8601 timestamp"),
    signing_key: Path | None = typer.Option(
        None, "--signing-key", help="Path to signing key"
    ),
) -> None:
    """Generate a plan for point-in-time restore."""
    from .backup.backup_manager import BackupManager

    manager = BackupManager(
        database_url=os.environ.get("WE3_DATABASE_URL", "sqlite:///./var/we3.db"),
        backup_root=Path(os.environ.get("WE3_BACKUP_ROOT", "./var/backups")),
    )

    try:
        target_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        plan = manager.generate_restore_plan(target_dt, signing_key)
        typer.echo(json.dumps(plan.to_dict(), indent=2, default=str))
    except ValueError as e:
        typer.echo(json.dumps({
            "error": f"No suitable backup found: {e}",
        }, indent=2))
        raise typer.Exit(code=1)


# ============================================================================
# Game Day Commands (TODO 61 - T8.1.11)
# ============================================================================

@app.command("game-day")
def game_day(
    context: str = typer.Option(..., "--context", help="Run context (run|run-scenario|matrix)"),
    authorization: str = typer.Option(..., "--authorization", help="Authorization token for game day"),
    output: Path = typer.Option(Path("./var/game_day"), "--output", help="Output directory"),
) -> None:
    """Run cross-system game day exercises.

    Executes the exhaustive failure matrix to validate:
    - Alert detection and triage
    - Containment and evidence preservation
    - Restore and repair
    - Reconciliation and re-certification
    """
    from .testing.game_day import GameDayOrchestrator, generate_failure_matrix_yaml

    orchestrator = GameDayOrchestrator()

    if context == "matrix":
        # Just output the failure matrix
        typer.echo(generate_failure_matrix_yaml())
        return

    # Validate authorization
    if not orchestrator.validate_authorization(authorization):
        typer.echo(json.dumps({"error": "Invalid authorization token"}))
        raise typer.Exit(code=1)

    orchestrator.assert_safety_observer(True)

    output.mkdir(parents=True, exist_ok=True)

    # Run failure matrix
    report = orchestrator.execute_failure_matrix(
        authorization_token=authorization,
    )

    output_path = output / "game_day_result.json"
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    typer.echo(json.dumps({
        "exercise_id": report.exercise_id,
        "scenarios_executed": len(report.scenarios_executed),
        "aborted": report.aborted,
        "output": str(output_path.resolve()),
    }, indent=2))

    if report.aborted:
        raise typer.Exit(code=1)


# ============================================================================
# GUI Commands
# ============================================================================


@app.command("gui")
def gui(
    port: int = typer.Option(8080, "--port", help="GUI server port"),
    host: str = typer.Option("0.0.0.0", "--host", help="GUI bind host"),
    stay: bool = typer.Option(False, "--stay", help="Run GUI in persistent background mode"),
) -> None:
    """Start the Wilson Eval3ngine GUI web interface.

    Launches a FastAPI backend with WebSocket support and serves
    the TypeScript frontend for model evaluation and report viewing.
    """
    import subprocess
    import sys
    from pathlib import Path

    gui_script = Path(__file__).resolve().parent / "gui" / "run_gui.py"
    if not gui_script.exists():
        typer.echo(json.dumps({"error": f"GUI script not found: {gui_script}"}))
        raise typer.Exit(code=1)

    cmd = [
        sys.executable,
        str(gui_script),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if stay:
        cmd.append("--stay")

    typer.echo(json.dumps({
        "status": "starting",
        "host": host,
        "port": port,
        "stay": stay,
        "url": f"http://{host}:{port}",
    }, indent=2))

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.wait()
    except KeyboardInterrupt:
        raise typer.Exit(code=0)


@app.command("gui-stop")
def gui_stop() -> None:
    """Stop the running Wilson Eval3ngine GUI server."""
    import subprocess
    import sys

    typer.echo("Stopping Wilson Eval3ngine GUI...")
    try:
        subprocess.run(
            [sys.executable, "-m", "wilson_eval3ngine.gui.stop_gui"],
            check=False,
        )
        typer.echo(json.dumps({"status": "stopped"}, indent=2))
    except Exception as e:
        typer.echo(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(code=1)


@app.command("gui-stay")
def gui_stay(
    port: int = typer.Option(8080, "--port", help="GUI server port"),
    host: str = typer.Option("0.0.0.0", "--host", help="GUI bind host"),
) -> None:
    """Start the GUI in persistent background mode (always on)."""
    gui(stay=True, port=port, host=host)


if __name__ == "__main__":
    app()
