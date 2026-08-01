from __future__ import annotations

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
from ..domain.io import load_experiment
from ..domain.enums import OperationState
from ..persistence.database import Database, Repository
from ..security.error_handling import ErrorSanitizer
from ..security.input_validation import (
    IdempotencyKeyValidator,
    ProjectIdValidator,
    ValidationError,
)
from ..telemetry import get_correlation_context
from ..observability import get_trace_id
from ..util import new_id, utc_now
from .auth import RequestContext, make_context_dependency
from .middleware import (
    add_production_middleware,
    get_health_registry,
)
from .operations import (
    add_operation_endpoints,
    compute_etag,
    get_idempotency_store,
)

logger = logging.getLogger("wilson.api.main")


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


def create_app(settings: Settings | None = None, *, database: Database | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    runtime.validate_for_production()
    context_dependency = make_context_dependency(runtime)
    operations = OperationRegistry()
    if database is None:
        database = Database(runtime.database_url)
        database.initialize()
    repository = Repository(database)
    idempotency_store = get_idempotency_store()

    # Track startup time for uptime reporting
    start_time = time.monotonic()

    # Graceful shutdown via lifespan context manager
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
        # Close database connections
        database.engine.dispose()
        logger.info("shutdown_complete", extra={"structured": {"event": "shutdown_complete"}})

    app = FastAPI(
        title="Wilson Eval3ngine API",
        version="0.1.0",
        description=(
            "Foundation API. It validates contracts and exposes a development "
            "operation wrapper around the synchronous deterministic runner."
        ),
        lifespan=lifespan,
    )
    app.state.settings = runtime
    app.state.operations = operations
    app.state.repository = repository
    app.state.idempotency_store = idempotency_store
    app.state.database = database
    app.state.start_time = start_time

    # Add production middleware (structured logging, security headers, rate limiting, body limits)
    redis_client = None
    if runtime.redis_url:
        try:
            import redis  # noqa: PLC0415
            redis_client = redis.from_url(runtime.redis_url)
            logger.info("redis_connected", extra={"url": runtime.redis_url})
        except ImportError:
            logger.warning("redis_package_not_installed_rate_limiting_in_memory")
        except Exception as e:
            logger.error("redis_connection_failed", extra={"error": str(e)})

    add_production_middleware(
        app,
        database_url=runtime.database_url,
        artifact_root=str(runtime.artifact_root),
        auth_mode=runtime.auth_mode,
        redis_client=redis_client,
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Liveness probe - returns 200 if the process is alive."""
        return {
            "status": "ok",
            "schema_version": "we3.health.v1",
            "environment": runtime.environment,
        }

    @app.get("/ready")
    def readiness() -> dict[str, Any]:
        """Readiness probe - checks all critical dependencies.

        Returns 200 if all critical health checks pass, 503 otherwise.
        Used by Kubernetes/deployment orchestrators to determine if
        the service is ready to receive traffic.
        """
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
        """Prometheus-compatible metrics endpoint.

        Returns metrics in Prometheus text exposition format.
        Rate limited to prevent abuse.
        """
        registry = get_health_registry()
        health_results = registry.run_all()

        lines: list[str] = []

        # Process info
        lines.append("# HELP we3_info Platform information")
        lines.append("# TYPE we3_info gauge")
        lines.append(
            f'we3_info{{environment="{runtime.environment}",version="0.1.0"}} 1'
        )

        # Uptime
        lines.append("# HELP we3_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE we3_uptime_seconds gauge")
        lines.append(f"we3_uptime_seconds {round(time.monotonic() - app.state.start_time, 2)}")

        # Health check metrics
        lines.append("# HELP we3_health_check Health check status (1=pass, 0=fail)")
        lines.append("# TYPE we3_health_check gauge")
        for name, check in health_results["checks"].items():
            value = 1 if check["status"] == "pass" else 0
            lines.append(f'we3_health_check{{name="{name}",critical="{str(check["critical"]).lower()}"}} {value}')

        # Operation counts
        lines.append("# HELP we3_operations_total Total operations by state")
        lines.append("# TYPE we3_operations_total counter")
        op_states: dict[str, int] = {}
        for op in operations._operations.values():
            state = op.state.value if hasattr(op.state, "value") else str(op.state)
            op_states[state] = op_states.get(state, 0) + 1
        for state, count in op_states.items():
            lines.append(f'we3_operations_total{{state="{state}"}} {count}')

        # Database connection pool metrics
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

        body = "\n".join(lines) + "\n"
        return Response(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

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
        request: RunRequest,
        context: RequestContext,
    ) -> None:
        operations.update(operation_id, state=OperationState.RUNNING)
        try:
            service = EvaluationService(
                database=database,
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
                safe_detail=ErrorSanitizer.sanitize_exception(exc),
            )

    @app.post("/v1/experiments:run", status_code=status.HTTP_202_ACCEPTED)
    def run_experiment(
        run_request: RunRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        """Run an experiment with idempotent operation handling."""
        # Check role
        if context.role not in {"evaluation_engineer", "project_admin"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": "evaluation_engineer or project_admin is required",
                    "schema_version": "we3.error.v1",
                    "trace_id": get_trace_id(),
                },
            )

        # Idempotency check with validation
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            try:
                validated_key = IdempotencyKeyValidator.validate(idempotency_key)
            except ValidationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "invalid_idempotency_key",
                        "retryable": False,
                        "safe_detail": "Idempotency key contains invalid characters",
                        "schema_version": "we3.error.v1",
                        "trace_id": get_trace_id(),
                    },
                )
            existing = idempotency_store.get(validated_key, context.project_id)
            if existing:
                operation = operations.get(existing.operation_id, project_id=context.project_id)
                if operation:
                    return {
                        "schema_version": "we3.operation_ack.v1",
                        "trace_id": get_trace_id(),
                        "project_id": context.project_id,
                        "operation": operation.model_dump(mode="json"),
                        "idempotent": True,
                    }

        try:
            manifest = load_experiment(run_request.manifest_path)
        except Exception:
            # Manifest load failure - return trace_id for telemetry correlation
            return {
                "schema_version": "we3.operation_ack.v1",
                "trace_id": get_trace_id(),
                "project_id": context.project_id,
                "operation": None,
                "error": "manifest_load_failed",
            }
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
        operation = operations.create(
            run_request,
            project_id=context.project_id,
        )
        background_tasks.add_task(
            execute_operation,
            operation.operation_id,
            run_request,
            context,
        )

        # Store idempotency if key was provided
        if idempotency_key:
            try:
                import json
                request_bytes = json.dumps(run_request.model_dump()).encode()
                idempotency_store.create(idempotency_key, context.project_id, request_bytes)
            except Exception:
                pass  # Don't fail on idempotency storage errors

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
        # Include ETag for state verification
        etag = compute_etag(operation_id, operation.state.value)
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

    # Add extended operation endpoints
    add_operation_endpoints(
        app,
        context_dependency,
        operations,
        repository,
        idempotency_store,
    )

    return app


app = create_app()
