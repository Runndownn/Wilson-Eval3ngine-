from __future__ import annotations

from pathlib import Path
import json

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

app = typer.Typer(
    name="we3",
    help="Wilson Eval3ngine foundation CLI.",
    no_args_is_help=True,
)


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


if __name__ == "__main__":
    app()
