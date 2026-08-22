from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wilson_eval3ngine.api.auth import RequestContext
from wilson_eval3ngine.api.operations import IdempotencyStore, add_operation_endpoints
from wilson_eval3ngine.security.authorization import (
    AuthorizationError,
    check_authorization,
)


class _Repository:
    def get_experiment(self, project_id: str, experiment_id: str):
        if project_id == "proj_test" and experiment_id == "exp_test":
            return {"id": experiment_id, "project_id": project_id}
        return None


@dataclass
class _Operation:
    operation_id: str
    project_id: str
    manifest_path: str
    output_dir: str
    state: str = "pending"

    def model_dump(self, *, mode: str = "python") -> dict[str, str]:
        del mode
        return {
            "operation_id": self.operation_id,
            "project_id": self.project_id,
            "manifest_path": self.manifest_path,
            "output_dir": self.output_dir,
            "state": self.state,
        }


class _Operations:
    def __init__(self) -> None:
        self._items: dict[str, _Operation] = {}

    def create(
        self,
        request,
        *,
        project_id: str,
        operation_id: str | None = None,
    ) -> _Operation:
        assert operation_id is not None
        operation = _Operation(
            operation_id=operation_id,
            project_id=project_id,
            manifest_path=request.manifest_path,
            output_dir=request.output_dir,
        )
        self._items[operation_id] = operation
        return operation

    def get(self, operation_id: str, *, project_id: str) -> _Operation | None:
        operation = self._items.get(operation_id)
        if operation is None or operation.project_id != project_id:
            return None
        return operation


def _app_for(role: str) -> FastAPI:
    app = FastAPI()

    def context_dependency() -> RequestContext:
        return RequestContext(
            project_id="proj_test",
            role=role,
            actor_id="actor_test",
            auth_method="oidc",
        )

    add_operation_endpoints(
        app,
        context_dependency,
        _Operations(),
        _Repository(),
        IdempotencyStore(),
    )
    return app


def test_experiment_execution_actions_have_explicit_matrix_grants() -> None:
    assert check_authorization(
        "evaluation_engineer", "experiments", "start", project_id="proj_test"
    ) is True
    assert check_authorization(
        "evaluation_engineer", "experiments", "regrade", project_id="proj_test"
    ) is True
    assert check_authorization(
        "project_admin", "experiments", "start", project_id="proj_test"
    ) is True
    with pytest.raises(AuthorizationError):
        check_authorization(
            "viewer", "experiments", "start", project_id="proj_test"
        )


def test_viewer_generic_export_permission_cannot_generate_dossier() -> None:
    # Viewer intentionally retains the generic report-export capability.
    assert check_authorization(
        "viewer", "exports", "create", project_id="proj_test"
    ) is True

    response = TestClient(_app_for("viewer")).post("/v1/dossiers:generate")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "unauthorized"


def test_release_authority_can_generate_dossier() -> None:
    response = TestClient(_app_for("release_authority")).post(
        "/v1/dossiers:generate"
    )
    assert response.status_code == 202
    assert response.json()["status"] == "generating_dossier"


def test_start_reserves_idempotency_binding_before_operation_creation() -> None:
    client = TestClient(_app_for("evaluation_engineer"))
    headers = {"Idempotency-Key": "start-exp-test-1"}

    first = client.post("/v1/experiments/exp_test:start", headers=headers)
    second = client.post("/v1/experiments/exp_test:start", headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["idempotent"] is True
    assert (
        first.json()["operation"]["operation_id"]
        == second.json()["operation"]["operation_id"]
    )
    assert first.json()["operation"]["state"] == "pending"
