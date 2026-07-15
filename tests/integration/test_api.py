from fastapi.testclient import TestClient

from wilson_eval3ngine.api.main import OperationRegistry, RunRequest, create_app
from wilson_eval3ngine.config import Settings
from wilson_eval3ngine.domain.io import load_experiment


def test_validate_endpoint_enforces_project_context(tmp_path, foundation_manifest):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))
    manifest = load_experiment(foundation_manifest).model_dump(mode="json", by_alias=True)

    ok = client.post(
        "/v1/experiments:validate",
        json=manifest,
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["valid"] is True

    denied = client.post(
        "/v1/experiments:validate",
        json=manifest,
        headers={
            "X-WE3-Project-ID": "another-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert denied.status_code == 403


def test_run_endpoint_rejects_manifest_from_another_project(
    tmp_path, foundation_manifest
):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-run.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    denied = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "another-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "project_context_mismatch"


def test_operation_registry_is_project_scoped():
    registry = OperationRegistry()
    request = RunRequest(manifest_path="manifest.yaml", output_dir="output")
    operation = registry.create(request, project_id="project-a")

    assert registry.get(
        operation.operation_id,
        project_id="project-a",
    ) == operation
    assert registry.get(
        operation.operation_id,
        project_id="project-b",
    ) is None
