from __future__ import annotations

from threading import Lock
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..application.service import EvaluationService
from ..config import Settings
from ..domain.contracts import ExperimentManifest, Operation
from ..domain.io import load_experiment
from ..domain.enums import OperationState
from ..persistence.database import Database, Repository
from ..util import new_id, utc_now
from .auth import RequestContext, make_context_dependency


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_path: str = Field(min_length=1)
    output_dir: str = Field(min_length=1)
    signing_key_path: str | None = None


class OperationRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._operations: dict[str, Operation] = {}

    def create(self, request: RunRequest, *, project_id: str) -> Operation:
        operation = Operation(
            operation_id=new_id("op"),
            project_id=project_id,
            manifest_path=request.manifest_path,
            output_dir=request.output_dir,
        )
        with self._lock:
            self._operations[operation.operation_id] = operation
        return operation

    def update(self, operation_id: str, **changes: Any) -> Operation:
        with self._lock:
            operation = self._operations[operation_id]
            for key, value in changes.items():
                setattr(operation, key, value)
            operation.updated_at = utc_now()
            return operation

    def get(self, operation_id: str, *, project_id: str) -> Operation | None:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None or operation.project_id != project_id:
                return None
            return operation


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    runtime.validate_for_production()
    context_dependency = make_context_dependency(runtime)
    operations = OperationRegistry()
    database = Database(runtime.database_url)
    database.initialize()
    repository = Repository(database)

    app = FastAPI(
        title="Wilson Eval3ngine API",
        version="0.1.0",
        description=(
            "Foundation API. It validates contracts and exposes a development "
            "operation wrapper around the synchronous deterministic runner."
        ),
    )
    app.state.settings = runtime
    app.state.operations = operations
    app.state.repository = repository

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": "we3.health.v1",
            "environment": runtime.environment,
        }

    @app.post("/v1/experiments:validate")
    def validate_experiment(
        manifest: ExperimentManifest,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        if manifest.project != context.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "project_context_mismatch",
                    "retryable": False,
                    "safe_detail": "manifest project does not match request context",
                },
            )
        return {
            "schema_version": "we3.validation_result.v1",
            "trace_id": new_id("trc"),
            "project_id": context.project_id,
            "valid": True,
            "manifest_sha256": manifest.content_hash(),
        }

    def execute_operation(
        operation_id: str,
        request: RunRequest,
        context: RequestContext,
    ) -> None:
        operations.update(operation_id, state=OperationState.RUNNING)
        try:
            service = EvaluationService(
                database_url=runtime.database_url,
                artifact_root=runtime.artifact_root,
            )
            outcome = service.run_manifest(
                request.manifest_path,
                output_dir=request.output_dir,
                signing_key_path=request.signing_key_path,
            )
            operations.update(
                operation_id,
                state=OperationState.SUCCEEDED,
                result_path=str(outcome.result_index_path),
            )
        except Exception as exc:
            operations.update(
                operation_id,
                state=OperationState.FAILED,
                error_code="operation_failed",
                safe_detail=str(exc)[:500],
            )

    @app.post("/v1/experiments:run", status_code=status.HTTP_202_ACCEPTED)
    def run_experiment(
        request: RunRequest,
        background_tasks: BackgroundTasks,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        if context.role not in {"evaluation_engineer", "project_admin"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "evaluation_engineer or project_admin is required",
                },
            )
        manifest = load_experiment(request.manifest_path)
        if manifest.project != context.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "project_context_mismatch",
                    "retryable": False,
                    "safe_detail": "manifest project does not match request context",
                },
            )
        operation = operations.create(request, project_id=context.project_id)
        background_tasks.add_task(
            execute_operation,
            operation.operation_id,
            request,
            context,
        )
        return {
            "schema_version": "we3.operation_ack.v1",
            "trace_id": new_id("trc"),
            "project_id": context.project_id,
            "operation": operation.model_dump(mode="json"),
        }

    @app.get("/v1/operations/{operation_id}")
    def get_operation(
        operation_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        operation = operations.get(operation_id, project_id=context.project_id)
        if operation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "operation_not_found",
                    "retryable": False,
                    "safe_detail": "operation does not exist",
                },
            )
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": new_id("trc"),
            "project_id": context.project_id,
            "operation": operation.model_dump(mode="json"),
        }

    @app.get("/v1/experiments/{experiment_id}")
    def get_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist in this project",
                },
            )
        return {
            "schema_version": "we3.experiment_view.v1",
            "trace_id": new_id("trc"),
            "project_id": context.project_id,
            "experiment": experiment,
        }

    return app


app = create_app()
