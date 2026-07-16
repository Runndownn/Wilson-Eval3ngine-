import json
import tempfile

from typer.testing import CliRunner

from wilson_eval3ngine.cli import (
    app,
    EXIT_SUCCESS,
    EXIT_WARNING,
    EXIT_BLOCK,
    EXIT_INDETERMINATE,
    EXIT_VALIDATION_ERROR,
    EXIT_PLATFORM_FAILURE,
)


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
    assert completed.exit_code == EXIT_INDETERMINATE, completed.output
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
    assert rejected.exit_code == EXIT_BLOCK
    assert json.loads(rejected.output)["valid"] is False


def test_cli_exit_codes_constant_values():
    """Verify exit codes match requirements."""
    assert EXIT_SUCCESS == 0
    assert EXIT_WARNING == 10
    assert EXIT_BLOCK == 20
    assert EXIT_INDETERMINATE == 30
    assert EXIT_VALIDATION_ERROR == 40
    assert EXIT_PLATFORM_FAILURE == 50


def test_cli_version_output():
    """Verify version command outputs proper JSON."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert "schema_version" in output
    assert output["schema_version"] == "we3.version.v1"
    assert output["cli_version"] == "0.1.0"


def test_cli_validate_outputs_schema_version():
    """Validate command outputs schema_version for machine parsing."""
    result = runner.invoke(app, ["validate", "examples/experiments/foundation.yaml"])
    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.validation_result.v1"


def test_cli_run_outputs_schema_version():
    """Run command outputs schema_version for machine parsing."""
    with tempfile.TemporaryDirectory() as tmp:
        foundation = "examples/experiments/foundation.yaml"
        result = runner.invoke(
            app,
            [
                "run",
                foundation,
                "--output",
                tmp,
                "--database-url",
                f"sqlite:///{tmp}/cli.db",
                "--artifact-root",
                tmp,
            ],
        )
        output = json.loads(result.output)
        assert output.get("schema_version") == "we3.experiment_result.v1"


def test_cli_export_validation_error_exit_code():
    """Export with invalid type returns validation error exit code."""
    result = runner.invoke(app, ["export", "--type", "invalid_type"])
    assert result.exit_code == EXIT_VALIDATION_ERROR
    output = json.loads(result.output)
    assert output.get("error") == "invalid_export_type"


def test_cli_export_missing_experiment_exit_code():
    """Export without experiment returns validation error exit code."""
    result = runner.invoke(app, ["export", "--type", "dossier"])
    assert result.exit_code == EXIT_VALIDATION_ERROR
    output = json.loads(result.output)
    assert output.get("error") == "missing_required"


def test_cli_regrade_validation_error_exit_code():
    """Regrade without required params returns validation error exit code."""
    result = runner.invoke(app, ["regrade"])
    assert result.exit_code == EXIT_VALIDATION_ERROR
    output = json.loads(result.output)
    assert output.get("error") == "missing_required"


def test_cli_status_command():
    """Status command returns proper structure."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.status.v1"
    assert "project_id" in output
    assert "status" in output


def test_cli_compare_command(tmp_path):
    """Compare command validates inputs."""
    # Compare with missing required paths - typer will show error
    result = runner.invoke(app, ["compare"])
    # Typer returns exit code 2 for missing required options
    assert result.exit_code == 2


def test_cli_json_output_flag():
    """--json flag enables machine-readable output."""
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert "schema_version" in output


def test_cli_export_valid_types():
    """Export command accepts valid types."""
    for export_type in ["dossier", "report", "raw_evidence"]:
        result = runner.invoke(app, ["export", "--type", export_type, "--experiment", "exp_123"])
        assert result.exit_code == EXIT_SUCCESS, f"Failed for type {export_type}"
        output = json.loads(result.output)
        assert output.get("export_type") == export_type


def test_cli_regrade_with_params():
    """Regrade command accepts valid params."""
    result = runner.invoke(app, ["regrade", "--experiment", "exp_123", "--grader-version", "1.0.0"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.regrade_ack.v1"
    assert output.get("experiment_id") == "exp_123"


def test_cli_plan_command(foundation_manifest):
    """Plan command generates estimate with schema_version."""
    result = runner.invoke(app, ["plan", str(foundation_manifest)])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.plan_estimate.v1"
    assert "total_runs" in output
    assert output["total_runs"] > 0


def test_cli_pause_command():
    """Pause command returns proper acknowledgment."""
    result = runner.invoke(app, ["pause", "--operation", "op_123"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.operation_ack.v1"
    assert output.get("operation_id") == "op_123"
    assert output.get("status") == "pause_requested"


def test_cli_resume_command():
    """Resume command returns proper acknowledgment."""
    result = runner.invoke(app, ["resume", "--operation", "op_123"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.operation_ack.v1"
    assert output.get("operation_id") == "op_123"
    assert output.get("status") == "resume_requested"


def test_cli_cancel_command():
    """Cancel command returns proper acknowledgment."""
    result = runner.invoke(app, ["cancel", "--operation", "op_123"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert output.get("schema_version") == "we3.operation_ack.v1"
    assert output.get("operation_id") == "op_123"
    assert output.get("status") == "cancel_requested"


def test_cli_plan_json_output(foundation_manifest):
    """Plan command with --json outputs machine-readable format."""
    result = runner.invoke(app, ["plan", str(foundation_manifest), "--json"])
    assert result.exit_code == EXIT_SUCCESS
    output = json.loads(result.output)
    assert "schema_version" in output
    assert output.get("schema_version") == "we3.plan_estimate.v1"