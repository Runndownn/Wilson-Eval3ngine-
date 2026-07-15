import json

from typer.testing import CliRunner

from wilson_eval3ngine.cli import app


runner = CliRunner()


def test_cli_validate_and_export_schemas(tmp_path, foundation_manifest):
    validated = runner.invoke(app, ["validate", str(foundation_manifest)])
    assert validated.exit_code == 0, validated.output
    payload = json.loads(validated.output)
    assert payload["valid"] is True
    assert payload["test_cases"] == 8
    assert payload["prompt_families"] == 8

    schema_dir = tmp_path / "schemas"
    exported = runner.invoke(
        app,
        ["export-schemas", "--output", str(schema_dir)],
    )
    assert exported.exit_code == 0, exported.output
    result = json.loads(exported.output)
    assert len(result["written"]) == 9
    assert (schema_dir / "we3.experiment.v1.schema.json").exists()
    assert (schema_dir / "we3.gate_decision.v1.schema.json").exists()


def test_cli_run_and_verify_dossier(tmp_path, foundation_manifest):
    output_dir = tmp_path / "output"
    completed = runner.invoke(
        app,
        [
            "run",
            str(foundation_manifest),
            "--output",
            str(output_dir),
            "--database-url",
            f"sqlite:///{tmp_path / 'cli.db'}",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ],
    )
    assert completed.exit_code == 0, completed.output
    result = json.loads(completed.output)
    assert result["gate_statuses"]["mdl_mock_balanced"] == "indeterminate"

    dossier = output_dir / "release_dossier.json"
    verified = runner.invoke(app, ["verify-dossier", str(dossier)])
    assert verified.exit_code == 0, verified.output
    verification = json.loads(verified.output)
    assert verification["valid"] is True

    signed = json.loads(dossier.read_text(encoding="utf-8"))
    signed["project_id"] = "tampered-project"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(signed), encoding="utf-8")

    rejected = runner.invoke(app, ["verify-dossier", str(tampered)])
    assert rejected.exit_code == 1
    assert json.loads(rejected.output)["valid"] is False
