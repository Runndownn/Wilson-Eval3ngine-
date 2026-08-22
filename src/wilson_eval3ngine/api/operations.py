"""Versioned REST operations with durable idempotency and exact authorization.

The operation API treats an idempotency key as a security-relevant binding
between an authenticated project, one request intent, and one operation ID.
Staging/production use Redis as the shared authority; development can use a
bounded process-local store for hermetic tests.

The synchronous operation registry itself remains process-local. A durable
idempotency binding that outlives that registry is therefore never replayed as
new work: the API fails safely and leaves restart-resilient execution to the
PostgreSQL scheduler.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta
from threading import Lock
from types import SimpleNamespace
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from ..observability import get_trace_id
from ..persistence.database import Repository
from ..security.authorization import AuthorizationError, check_authorization
from ..security.input_validation import (
    IdempotencyKeyValidator,
    ProjectIdValidator,
    ValidationError,
)
from ..util import new_id, sha256_hex, utc_now
from .auth import RequestContext

logger = logging.getLogger("wilson.api.operations")


class IdempotencyConflict(RuntimeError):
    """Raised when one key is reused for a different request intent."""


class IdempotencyBackendUnavailable(RuntimeError):
    """Raised when the authoritative shared idempotency store is unavailable."""


class IdempotencyRecord(BaseModel):
    """Project-scoped binding between a request intent and operation."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    project_id: str
    operation_id: str
    request_hash: str
    created_at: datetime
    expires_at: datetime


class IdempotencyStore:
    """Redis-backed idempotency authority with a development fallback.

    Redis uses ``SET NX EX`` so concurrent workers cannot establish two
    successful bindings for the same project/key. Reuse is accepted only when
    the request-intent hash is identical.
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        *,
        fail_closed: bool = False,
        max_memory_records: int = 10_000,
    ) -> None:
        if max_memory_records <= 0:
            raise ValueError("max_memory_records must be positive")
        if fail_closed and redis_client is None:
            raise IdempotencyBackendUnavailable(
                "Redis is required for distributed idempotency"
            )
        self._redis = redis_client
        self._fail_closed = fail_closed
        self._max_memory_records = max_memory_records
        self._lock = Lock()
        self._records: dict[str, IdempotencyRecord] = {}

    @staticmethod
    def _validate(key: str, project_id: str) -> tuple[str, str]:
        try:
            return (
                IdempotencyKeyValidator.validate(key),
                ProjectIdValidator.validate(project_id),
            )
        except ValidationError as exc:
            raise ValueError("invalid idempotency scope") from exc

    @classmethod
    def _scoped_key(cls, key: str, project_id: str) -> str:
        key, project_id = cls._validate(key, project_id)
        digest = hashlib.sha256(f"{project_id}\0{key}".encode("utf-8")).hexdigest()
        return f"we3:idempotency:{digest}"

    def _redis_get(self, scoped_key: str) -> IdempotencyRecord | None:
        try:
            raw = self._redis.get(scoped_key)
        except Exception as exc:
            logger.error(
                "idempotency_backend_read_failed",
                extra={"error_class": type(exc).__name__},
            )
            if self._fail_closed:
                raise IdempotencyBackendUnavailable(
                    "distributed idempotency authority unavailable"
                ) from exc
            return None
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return IdempotencyRecord.model_validate_json(raw)
        except Exception as exc:
            raise IdempotencyBackendUnavailable(
                "distributed idempotency record is malformed"
            ) from exc

    def get(self, key: str, project_id: str) -> IdempotencyRecord | None:
        scoped_key = self._scoped_key(key, project_id)
        if self._redis is not None:
            return self._redis_get(scoped_key)

        with self._lock:
            record = self._records.get(scoped_key)
            if record is None:
                return None
            if utc_now() > record.expires_at:
                del self._records[scoped_key]
                return None
            return record

    @staticmethod
    def _assert_same_intent(
        existing: IdempotencyRecord,
        request_hash: str,
    ) -> str:
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "idempotency key was already used for different request intent"
            )
        return existing.operation_id

    def create(
        self,
        key: str,
        project_id: str,
        payload_bytes: bytes,
        ttl_seconds: int = 86400,
        *,
        operation_id: str | None = None,
    ) -> str:
        """Atomically bind a key to request intent and an operation ID."""
        if ttl_seconds <= 0:
            raise ValueError("idempotency TTL must be positive")
        key, project_id = self._validate(key, project_id)
        scoped_key = self._scoped_key(key, project_id)
        request_hash = sha256_hex(payload_bytes)
        bound_operation_id = operation_id or new_id("op")
        now = utc_now()
        record = IdempotencyRecord(
            idempotency_key=key,
            project_id=project_id,
            operation_id=bound_operation_id,
            request_hash=request_hash,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

        if self._redis is not None:
            try:
                created = self._redis.set(
                    scoped_key,
                    record.model_dump_json(),
                    ex=ttl_seconds,
                    nx=True,
                )
            except Exception as exc:
                logger.error(
                    "idempotency_backend_write_failed",
                    extra={"error_class": type(exc).__name__},
                )
                if self._fail_closed:
                    raise IdempotencyBackendUnavailable(
                        "distributed idempotency authority unavailable"
                    ) from exc
                created = False
            if created:
                return bound_operation_id
            existing = self._redis_get(scoped_key)
            if existing is None:
                if self._fail_closed:
                    raise IdempotencyBackendUnavailable(
                        "idempotency binding could not be established"
                    )
                return self._memory_create(record)
            return self._assert_same_intent(existing, request_hash)

        return self._memory_create(record)

    def _memory_create(self, record: IdempotencyRecord) -> str:
        scoped_key = self._scoped_key(record.idempotency_key, record.project_id)
        with self._lock:
            existing = self._records.get(scoped_key)
            if existing is not None and utc_now() <= existing.expires_at:
                return self._assert_same_intent(existing, record.request_hash)
            if existing is not None:
                del self._records[scoped_key]
            if len(self._records) >= self._max_memory_records:
                oldest_key = min(
                    self._records,
                    key=lambda item: self._records[item].created_at,
                )
                del self._records[oldest_key]
            self._records[scoped_key] = record
            return record.operation_id


_idempotency_store: IdempotencyStore | None = None
_idempotency_store_lock = Lock()


def get_idempotency_store() -> IdempotencyStore:
    """Get the process singleton, using Redis in assurance environments."""
    global _idempotency_store
    with _idempotency_store_lock:
        if _idempotency_store is not None:
            return _idempotency_store

        environment = os.environ.get("WE3_ENVIRONMENT", "development").strip().lower()
        assurance = environment in {"staging", "production"}
        redis_url = os.environ.get("WE3_REDIS_URL", "").strip()
        redis_client = None
        if redis_url:
            try:
                import redis

                redis_client = redis.from_url(redis_url)
                if assurance:
                    redis_client.ping()
            except Exception as exc:
                logger.error(
                    "idempotency_redis_unavailable",
                    extra={"error_class": type(exc).__name__},
                )
                if assurance:
                    raise IdempotencyBackendUnavailable(
                        "Redis idempotency authority is unavailable"
                    ) from exc
                redis_client = None
        elif assurance:
            raise IdempotencyBackendUnavailable(
                "staging/production requires Redis-backed idempotency"
            )

        _idempotency_store = IdempotencyStore(
            redis_client=redis_client,
            fail_closed=assurance,
        )
        return _idempotency_store


class CursorPage(BaseModel):
    """Cursor-based pagination response."""

    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    next_cursor: str | None = None
    has_more: bool = False
    total_hint: int | None = None


def encode_cursor(*values: str) -> str:
    raw = ":".join(values)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def decode_cursor(cursor: str) -> list[str]:
    return [cursor]


def compute_etag(*items: Any) -> str:
    combined = sha256_hex(str([str(i) for i in items]))
    return f'W/"{combined[:16]}"'


def _authorization_denied(detail: str, exc: AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "unauthorized",
            "retryable": False,
            "safe_detail": detail,
            "trace_id": get_trace_id(),
            "schema_version": "we3.error.v1",
        },
    )


def _idempotency_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "idempotency_unavailable",
            "retryable": True,
            "safe_detail": "idempotency authority is unavailable",
            "trace_id": get_trace_id(),
            "schema_version": "we3.error.v1",
        },
    )


def _require_experiment(
    repository: Repository,
    project_id: str,
    experiment_id: str,
) -> Any:
    experiment = repository.get_experiment(project_id, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "experiment_not_found",
                "retryable": False,
                "safe_detail": "experiment does not exist in this project",
                "trace_id": get_trace_id(),
                "schema_version": "we3.error.v1",
            },
        )
    return experiment


def add_operation_endpoints(
    app: FastAPI,
    context_dependency: Any,
    operations: Any,
    repository: Repository,
    idempotency_store: IdempotencyStore,
) -> None:
    """Add project-authorized operation endpoints to the API."""

    @app.post("/v1/experiments/{experiment_id}:start", status_code=status.HTTP_202_ACCEPTED)
    def start_experiment(
        experiment_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        del background_tasks
        try:
            check_authorization(
                context.role,
                "experiments",
                "start",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot start experiment", exc) from exc

        _require_experiment(repository, context.project_id, experiment_id)
        idempotency_key = request.headers.get("Idempotency-Key")
        request_intent = f"start:{context.project_id}:{experiment_id}".encode("utf-8")
        request_hash = sha256_hex(request_intent)

        if idempotency_key:
            try:
                existing = idempotency_store.get(idempotency_key, context.project_id)
            except (IdempotencyBackendUnavailable, ValueError) as exc:
                if isinstance(exc, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "invalid_idempotency_key",
                            "retryable": False,
                            "safe_detail": "idempotency key is invalid",
                            "trace_id": get_trace_id(),
                            "schema_version": "we3.error.v1",
                        },
                    ) from exc
                raise _idempotency_unavailable(exc) from exc

            if existing is not None:
                if existing.request_hash != request_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "idempotency_conflict",
                            "retryable": False,
                            "safe_detail": "idempotency key is bound to different request intent",
                            "trace_id": get_trace_id(),
                            "schema_version": "we3.error.v1",
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
                            "trace_id": get_trace_id(),
                            "schema_version": "we3.error.v1",
                        },
                    )
                return {
                    "schema_version": "we3.operation_ack.v1",
                    "trace_id": get_trace_id(),
                    "project_id": context.project_id,
                    "operation": operation.model_dump(mode="json"),
                    "idempotent": True,
                }

        proposed_operation_id = new_id("op")
        if idempotency_key:
            try:
                bound_operation_id = idempotency_store.create(
                    idempotency_key,
                    context.project_id,
                    request_intent,
                    operation_id=proposed_operation_id,
                )
            except IdempotencyConflict as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "idempotency_conflict",
                        "retryable": False,
                        "safe_detail": "idempotency key is bound to different request intent",
                        "trace_id": get_trace_id(),
                        "schema_version": "we3.error.v1",
                    },
                ) from exc
            except IdempotencyBackendUnavailable as exc:
                raise _idempotency_unavailable(exc) from exc

            if bound_operation_id != proposed_operation_id:
                winner = operations.get(
                    bound_operation_id,
                    project_id=context.project_id,
                )
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
                        "trace_id": get_trace_id(),
                        "schema_version": "we3.error.v1",
                    },
                )

        operation = operations.create(
            SimpleNamespace(
                manifest_path=f"/experiments/{experiment_id}",
                output_dir=f"./var/output/{experiment_id}",
            ),
            project_id=context.project_id,
            operation_id=proposed_operation_id,
        )
        return {
            "schema_version": "we3.operation_ack.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "operation": operation.model_dump(mode="json"),
        }

    @app.post("/v1/experiments/{experiment_id}:pause", status_code=status.HTTP_202_ACCEPTED)
    def pause_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
        if_match: str | None = Header(None, alias="If-Match"),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "experiments",
                "update:own",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot pause experiment", exc) from exc
        _require_experiment(repository, context.project_id, experiment_id)
        if if_match and if_match != compute_etag(experiment_id, "state"):
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail={
                    "code": "etag_mismatch",
                    "retryable": True,
                    "safe_detail": "resource has been modified",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "paused",
        }

    @app.post("/v1/experiments/{experiment_id}:resume", status_code=status.HTTP_202_ACCEPTED)
    def resume_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "experiments",
                "update:own",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot resume experiment", exc) from exc
        _require_experiment(repository, context.project_id, experiment_id)
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "resumed",
        }

    @app.post("/v1/experiments/{experiment_id}:cancel", status_code=status.HTTP_202_ACCEPTED)
    def cancel_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "experiments",
                "update:own",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot cancel experiment", exc) from exc
        _require_experiment(repository, context.project_id, experiment_id)
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "cancelled",
        }

    @app.post("/v1/experiments/{experiment_id}:regrade", status_code=status.HTTP_202_ACCEPTED)
    def regrade_experiment(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "experiments",
                "regrade",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot regrade experiment", exc) from exc
        _require_experiment(repository, context.project_id, experiment_id)
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "regrading",
        }

    @app.get("/v1/experiments/{experiment_id}/runs")
    def list_experiment_runs(
        experiment_id: str,
        context: RequestContext = Depends(context_dependency),
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            check_authorization(
                context.role,
                "runs",
                "read",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot list runs", exc) from exc
        _require_experiment(repository, context.project_id, experiment_id)
        return {
            "schema_version": "we3.run_list.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "experiment_id": experiment_id,
            "runs": [],
            "next_cursor": None,
            "has_more": False,
            "etag": compute_etag(experiment_id, limit, cursor),
        }

    @app.get("/v1/metrics")
    def list_metrics(
        context: RequestContext = Depends(context_dependency),
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        del cursor, limit
        try:
            check_authorization(
                context.role,
                "metrics",
                "read",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot read metrics", exc) from exc
        return {
            "schema_version": "we3.metric_list.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "metrics": [],
            "next_cursor": None,
            "has_more": False,
        }

    @app.post("/v1/dossiers:generate", status_code=status.HTTP_202_ACCEPTED)
    def generate_dossier(
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        # Dossier generation is a release-evidence capability. Generic report
        # export permission is intentionally not accepted as a fallback.
        try:
            check_authorization(
                context.role,
                "exports",
                "create:dossier",
                project_id=context.project_id,
            )
        except AuthorizationError as exc:
            raise _authorization_denied("cannot generate dossier", exc) from exc
        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "generating_dossier",
        }


__all__ = [
    "CursorPage",
    "IdempotencyBackendUnavailable",
    "IdempotencyConflict",
    "IdempotencyRecord",
    "IdempotencyStore",
    "add_operation_endpoints",
    "compute_etag",
    "decode_cursor",
    "encode_cursor",
    "get_idempotency_store",
]
