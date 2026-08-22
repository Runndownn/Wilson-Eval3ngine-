from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from ..application.service import EvaluationService
from ..config import Settings
from ..domain.contracts import ExperimentManifest, Operation
from ..domain.enums import OperationState
from ..domain.io import load_experiment
from ..observability import get_trace_id
from ..persistence.database import Database, Repository
from ..security.authorization import AuthorizationError, check_authorization
from ..security.error_handling import ErrorSanitizer
from ..security.input_validation import IdempotencyKeyValidator, ValidationError
from ..util import new_id, sha256_hex, utc_now
from .auth import RequestContext, make_context_dependency
from .middleware import add_production_middleware, get_health_registry
from .operations import (
    IdempotencyBackendUnavailable,
    IdempotencyConflict,
    IdempotencyStore,
    add_operation_endpoints,
    compute_etag,
)

logger = logging.getLogger("wilson.api.main")


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_path: str = Field(min_length=1)
    output_dir: str = Field(min_length=1)
    signing_key_path: str | None = None


class OperationRegistry:
    """Process-local operation view used by the synchronous API lane.

    Durable worker execution belongs to the PostgreSQL scheduler. This registry
    remains intentionally local, but callers can supply a pre-reserved operation
    ID so Redis idempotency and the returned operation refer to the same object.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._operations: dict[str, Operation] = {}

    def create(
        self,
        request: RunRequest | Any,
        *,
        project_id: str,
        operation_id: str | None = None,
    ) -> Operation:
        operation = Operation(
            operation_id=operation_id or new_id("op"),
            project_id=project_id,
            manifest_path=request.manifest_path,
            output_dir=request.output_dir,
        )
        with self._lock:
            if operation.operation_id in self._operations:
                raise ValueError("operation identifier already exists")
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

    def state_counts(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for operation in self._operations.values():
                state = (
                    operation.state.value
                    if hasattr(operation.state, "value")
                    else str(operation.state)
                )
                counts[state] = counts.get(state, 0) + 1
            return counts


def _build_redis_client(runtime: Settings) -> Any | None:
    if not runtime.redis_url:
        if runtime.is_assurance_environment:
            raise RuntimeError(
                "staging/production requires Redis-backed security state"
            )
        return None

    try:
        import redis
    except ImportError as exc:
        if runtime.is_assurance_environment:
            raise RuntimeError(
                "Redis package is required for production security state"
            ) from exc
        logger.warning("redis_package_not_installed_using_local_development_state")
        return None

    client = redis.from_url(runtime.redis_url)
    if runtime.is_assurance_environment:
        try:
            client.ping()
        except Exception as exc:
            raise RuntimeError(
                "Redis security-state authority is unavailable"
            ) from exc
    logger.info("redis_security_state_configured")
    return client


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
) -> FastAPI:
    runtime = settings or Settings.from_env()
    runtime.validate_for_production()
    operations = OperationRegistry()

    if database is None:
        database = Database(runtime.database_url)
        database.initialize()
    repository = Repository(database)

    redis_client = _build_redis_client(runtime)
    idempotency_store = IdempotencyStore(
        redis_client=redis_client,
        fail_closed=runtime.is_assurance_environment,
    )
    context_dependency = make_context_dependency(runtime)
    start_time = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "startup_complete",
            extra={
                "structured": {
                    "event": "startup_complete",
                    "environment": runtime.environment,
                }
            },
        )
        yield
        logger.info(
            "shutdown_initiated",
            extra={
                "structured": {
                    "event": "shutdown_initiated",
                    "uptime_seconds": round(time.monotonic() - start_time, 2),
                }
            },
        )
        database.engine.dispose()
        logger.info(
            "shutdown_complete",
            extra={"structured": {"event": "shutdown_complete"}},
        )

    # Interactive schemas are useful in local development but expand public
    # production reconnaissance surface. Operators can export the versioned
    # OpenAPI contract offline with the repository's export command instead.
    assurance = runtime.is_assurance_environment
    app = FastAPI(
        title="Wilson Eval3ngine API",
        version="0.2.0",
        description=(
            "Evidence-oriented evaluation API with project-scoped identity, "
            "bounded execution, and explicit security/assurance boundaries."
        ),
        lifespan=lifespan,
        docs_url=None if assurance else "/docs",
        redoc_url=None if assurance else "/redoc",
        openapi_url=None if assurance else "/openapi.json",
    )
    app.state.settings = runtime
    app.state.operations = operations
    app.state.repository = repository
    app.state.idempotency_store = idempotency_store
    app.state.database = database
    app.state.redis_client = redis_client
    app.state.start_time = start_time

    add_production_middleware(
        app,
        database_url=runtime.database_url,
        artifact_root=str(runtime.artifact_root),
        auth_mode=runtime.auth_mode,
        redis_client=redis_client,
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": "we3.health.v1",
            "environment": runtime.environment,
        }

    @app.get("/ready")
    def readiness() -> JSONResponse:
        registry = get_health_registry()
        results = registry.run_all()
        status_code = 200 if not results["critical_failures"] else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "schema_version": "we3.readiness.v1",
                "status": "ready" if status_code == 200 else "not_ready",
                "environment": runtime.environment,
                "uptime_seconds": round(time.monotonic() - app.state.start_time, 2),
                "checks": results["checks"],
                "critical_failures": results["critical_failures"],
            },
        )

    @app.get("/metrics")
    def metrics() -> Response:
        registry = get_health_registry()
        health_results = registry.run_all()
        lines: list[str] = []

        lines.append("# HELP we3_info Platform information")
        lines.append("# TYPE we3_info gauge")
        lines.append(
            f'we3_info{{environment="{runtime.environment}",version="0.2.0"}} 1'
        )
        lines.append("# HELP we3_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE we3_uptime_seconds gauge")
        lines.append(
            f"we3_uptime_seconds {round(time.monotonic() - app.state.start_time, 2)}"
        )
        lines.append("# HELP we3_health_check Health check status (1=pass, 0=fail)")
        lines.append("# TYPE we3_health_check gauge")
        for name, check in health_results["checks"].items():
            value = 1 if check["status"] == "pass" else 0
            lines.append(
                f'we3_health_check{{name="{name}",critical="{str(check["critical"]).lower()}"}} {value}'
            )

        lines.append("# HELP we3_operations_total Total operations by state")
        lines.append("# TYPE we3_operations_total counter")
        for state_name, count in operations.state_counts().items():
            lines.append(f'we3_operations_total{{state="{state_name}"}} {count}')

        try:
            pool = database.engine.pool
            lines.append("# HELP we3_db_pool_size Database connection pool size")
            lines.append("# TYPE we3_db_pool_size gauge")
            lines.append(f"we3_db_pool_size {pool.size()}")
            lines.append("# HELP we3_db_pool_checkedout Database connections checked out")
            lines.append("# TYPE we3_db_pool_checkedout gauge")
            lines.append(f"we3_db_pool_checkedout {pool.checkedout()}")
            lines.append("# HELP we3_db_pool_overflow Database connection overflow")
            lines.append("# TYPE we3_db_pool_overflow gauge")
            lines.append(f"we3_db_pool_overflow {pool.overflow()}")
        except Exception:
            pass

        return Response(
            content="\n".join(lines) + "\n",
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.post("/v1/experiments:validate")
    def validate_experiment(
        manifest: ExperimentManifest,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        # Validation accepts caller-supplied data without mutating project state,
        # but it still requires a role that can read the target project model.
        try:
            check_authorization(
                context.role,
                "experiments",
                "read",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "experiment validation is not permitted",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            ) from exc

        if manifest.project != context.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "project_context_mismatch",
                    "retryable": False,
                    "safe_detail": "manifest project does not match request context",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            )
        return {
            "schema_version": "we3.validation_result.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "valid": True,
            "manifest_sha256": manifest.content_hash(),
        }

    def execute_operation(
        operation_id: str,
        run_request: RunRequest,
        context: RequestContext,
    ) -> None:
        operations.update(operation_id, state=OperationState.RUNNING)
        try:
            service = EvaluationService(
                database=database,
                artifact_root=runtime.artifact_root,
            )
            outcome = service.run_manifest(
                run_request.manifest_path,
                output_dir=run_request.output_dir,
                signing_key_path=run_request.signing_key_path,
            )
            operations.update(
                operation_id,
                state=OperationState.SUCCEEDED,
                result_path=str(outcome.result_index_path),
            )
        except Exception as exc:
            logger.exception(
                "operation_execution_failed",
                extra={
                    "operation_id": operation_id,
                    "error_class": type(exc).__name__,
                },
            )
            operations.update(
                operation_id,
                state=OperationState.FAILED,
                error_code="operation_failed",
                safe_detail=ErrorSanitizer.sanitize_exception(exc),
            )

    @app.post("/v1/experiments:run", status_code=status.HTTP_202_ACCEPTED)
    def run_experiment(
        run_request: RunRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "runs",
                "create",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "experiment execution is not permitted",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            ) from exc

        try:
            manifest = load_experiment(run_request.manifest_path)
        except Exception as exc:
            logger.info(
                "manifest_load_rejected",
                extra={"error_class": type(exc).__name__},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "manifest_load_failed",
                    "retryable": False,
                    "safe_detail": "experiment manifest could not be loaded",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            ) from exc

        if manifest.project != context.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "project_context_mismatch",
                    "retryable": False,
                    "safe_detail": "manifest project does not match request context",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            )

        request_bytes = json.dumps(
            run_request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        request_hash = sha256_hex(request_bytes)
        idempotency_key = request.headers.get("Idempotency-Key")
        validated_key: str | None = None

        if idempotency_key:
            try:
                validated_key = IdempotencyKeyValidator.validate(idempotency_key)
                existing = idempotency_store.get(
                    validated_key,
                    context.project_id,
                )
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "invalid_idempotency_key",
                        "retryable": False,
                        "safe_detail": "idempotency key is invalid",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                ) from exc
            except IdempotencyBackendUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "idempotency_unavailable",
                        "retryable": True,
                        "safe_detail": "idempotency authority is unavailable",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                ) from exc

            if existing is not None:
                if existing.request_hash != request_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "idempotency_conflict",
                            "retryable": False,
                            "safe_detail": "idempotency key is bound to different request intent",
                            "schema_version": "we3.error.v1",
                            "trace_id": get_trace_id(),
                        },
                    )
                operation = operations.get(
                    existing.operation_id,
                    project_id=context.project_id,
                )
                if operation is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "idempotency_operation_state_unavailable",
                            "retryable": True,
                            "safe_detail": "existing operation state is not available in this process",
                            "schema_version": "we3.error.v1",
                            "trace_id": get_trace_id(),
                        },
                    )
                return {
                    "schema_version": "we3.operation_ack.v1",
                    "trace_id": get_trace_id(),
                    "project_id": context.project_id,
                    "operation": operation.model_dump(mode="json"),
                    "idempotent": True,
                }

        operation_id = new_id("op")
        if validated_key is not None:
            try:
                bound_id = idempotency_store.create(
                    validated_key,
                    context.project_id,
                    request_bytes,
                    operation_id=operation_id,
                )
            except IdempotencyConflict as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "idempotency_conflict",
                        "retryable": False,
                        "safe_detail": "idempotency key is bound to different request intent",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                ) from exc
            except IdempotencyBackendUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "idempotency_unavailable",
                        "retryable": True,
                        "safe_detail": "idempotency authority is unavailable",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                ) from exc

            if bound_id != operation_id:
                winner = operations.get(bound_id, project_id=context.project_id)
                if winner is not None:
                    return {
                        "schema_version": "we3.operation_ack.v1",
                        "trace_id": get_trace_id(),
                        "project_id": context.project_id,
                        "operation": winner.model_dump(mode="json"),
                        "idempotent": True,
                    }
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "idempotency_race",
                        "retryable": True,
                        "safe_detail": "another request established this idempotency key first",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                )

        operation = operations.create(
            run_request,
            project_id=context.project_id,
            operation_id=operation_id,
        )
        background_tasks.add_task(
            execute_operation,
            operation.operation_id,
            run_request,
            context,
        )

        return {
            "schema_version": "we3.operation_ack.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "operation": operation.model_dump(mode="json"),
        }

    @app.get("/v1/operations/{operation_id}")
    def get_operation(
        operation_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "runs",
                "read",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "operation access is not permitted",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            ) from exc

        operation = operations.get(operation_id, project_id=context.project_id)
        if operation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "operation_not_found",
                    "retryable": False,
                    "safe_detail": "operation does not exist",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            )
        state_value = (
            operation.state.value
            if hasattr(operation.state, "value")
            else str(operation.state)
        )
        etag = compute_etag(operation_id, state_value)
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "operation": operation.model_dump(mode="json"),
            "etag": etag,
        }

    @app.get("/v1/experiments/{experiment_id}")
    def get_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "experiments",
                "read",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "experiment access is not permitted",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            ) from exc

        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist in this project",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            )
        etag = compute_etag(experiment_id, "experiment")
        return {
            "schema_version": "we3.experiment_view.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "experiment": experiment,
            "etag": etag,
        }

    add_operation_endpoints(
        app,
        context_dependency,
        operations,
        repository,
        idempotency_store,
    )

    return app


app = create_app()
