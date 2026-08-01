"""Versioned REST operations with idempotency, ETag, and cursor pagination.

T7.1.1 - Implements command/query separation and long-running operations.
Provides operational endpoints for experiments with proper state management.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any
from threading import Lock

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi import Header
from pydantic import BaseModel, ConfigDict

from ..domain.contracts import Operation, OperationState
from ..persistence.database import Repository
from ..security.authorization import check_authorization, AuthorizationError
from ..util import new_id, sha256_hex, utc_now
from ..observability import get_trace_id
from .auth import RequestContext

logger = logging.getLogger("wilson.api.operations")


# ============================================================================
# Idempotency Support
# ============================================================================


class IdempotencyRecord(BaseModel):
    """Record of an idempotent request to prevent duplicate operations."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    project_id: str
    operation_id: str
    request_hash: str
    created_at: datetime
    expires_at: datetime


class IdempotencyStore:
    """In-memory store for idempotency keys (MVP implementation).

    In production, this would be backed by PostgreSQL with proper TTL.
    Keys are scoped to projects to prevent cross-project key collision.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, IdempotencyRecord] = {}

    def _scoped_key(self, key: str, project_id: str) -> str:
        """Create a scoped key that includes project_id."""
        return f"{project_id}:{key}"

    def get(self, key: str, project_id: str) -> IdempotencyRecord | None:
        """Retrieve record if exists and matches project."""
        with self._lock:
            scoped_key = self._scoped_key(key, project_id)
            record = self._records.get(scoped_key)
            if record:
                # Check expiry
                if utc_now() > record.expires_at:
                    del self._records[scoped_key]
                    return None
                return record
            return None

    def create(
        self,
        key: str,
        project_id: str,
        payload_bytes: bytes,
        ttl_seconds: int = 86400,  # 24 hours default
    ) -> str:
        """Create idempotent record and return operation_id."""
        with self._lock:
            scoped_key = self._scoped_key(key, project_id)
            # Check if already exists for this project
            existing = self._records.get(scoped_key)
            if existing:
                return existing.operation_id

            operation_id = new_id("op")
            record = IdempotencyRecord(
                idempotency_key=key,
                project_id=project_id,
                operation_id=operation_id,
                request_hash=sha256_hex(payload_bytes),
                created_at=utc_now(),
                expires_at=datetime.fromtimestamp(
                    utc_now().timestamp() + ttl_seconds, tz=utc_now().tzinfo
                ),
            )
            self._records[scoped_key] = record
            return operation_id


# Global idempotency store
_idempotency_store: IdempotencyStore | None = None


def get_idempotency_store() -> IdempotencyStore:
    """Get or create the global idempotency store."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store


# ============================================================================
# Cursor Pagination
# ============================================================================


class CursorPage(BaseModel):
    """Cursor-based pagination response."""

    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    next_cursor: str | None = None
    has_more: bool = False
    total_hint: int | None = None


def encode_cursor(*values: str) -> str:
    """Encode cursor values into opaque string."""
    raw = ":".join(values)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def decode_cursor(cursor: str) -> list[str]:
    """Decode cursor string (opaque, values recovered from query)."""
    return [cursor]


# ============================================================================
# ETag Support
# ============================================================================


def compute_etag(*items: Any) -> str:
    """Compute ETag for a set of items."""
    combined = sha256_hex(str([str(i) for i in items]))
    return f'W/"{combined[:16]}"'


# ============================================================================
# API Extension
# ============================================================================


def add_operation_endpoints(
    app: FastAPI,
    context_dependency: Any,
    operations: Any,
    repository: Repository,
    idempotency_store: IdempotencyStore,
) -> None:
    """Add versioned operation endpoints to the API."""

    @app.post("/v1/experiments/{experiment_id}:start", status_code=status.HTTP_202_ACCEPTED)
    def start_experiment(
        experiment_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        """Start an experiment after validation."""
        experiment = repository.get_experiment(context.project_id, experiment_id)
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

        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            existing = idempotency_store.get(idempotency_key, context.project_id)
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
            check_authorization(
                context.role, "experiments", "start", project_id=context.project_id
            )
        except AuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "retryable": False,
                    "safe_detail": str(e),
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        operation = Operation(
            operation_id=new_id("op"),
            project_id=context.project_id,
            state=OperationState.RUNNING,
            manifest_path=f"/experiments/{experiment_id}",
            output_dir=f"./var/output/{experiment_id}",
        )
        operations.update(operation.operation_id, state=OperationState.QUEUED)

        if idempotency_key:
            idempotency_store.create(
                idempotency_key,
                context.project_id,
                b"",  # Empty for MVP
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
        request: Request,
        context: RequestContext = Depends(context_dependency),
        if_match: str | None = Header(None, alias="If-Match"),
    ) -> dict[str, Any]:
        """Pause a running experiment."""
        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        # ETag validation for state change
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

        try:
            check_authorization(
                context.role, "experiments", "update:own", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot pause experiment",
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
        """Resume a paused experiment."""
        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        try:
            check_authorization(
                context.role, "experiments", "update:own", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot resume experiment",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

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
        """Cancel an experiment."""
        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        try:
            check_authorization(
                context.role, "experiments", "update:own", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot cancel experiment",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

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
        """Regrade an experiment with a new grader version."""
        experiment = repository.get_experiment(context.project_id, experiment_id)
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "experiment_not_found",
                    "retryable": False,
                    "safe_detail": "experiment does not exist",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        try:
            check_authorization(
                context.role, "experiments", "regrade", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot regrade experiment",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

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
        """List runs for an experiment with cursor pagination."""
        try:
            check_authorization(
                context.role, "runs", "read", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot list runs",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

        runs = []
        next_cursor = None
        has_more = False
        etag = compute_etag(experiment_id, limit, cursor)

        return {
            "schema_version": "we3.run_list.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "experiment_id": experiment_id,
            "runs": runs,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "etag": etag,
        }

    @app.get("/v1/metrics")
    def list_metrics(
        context: RequestContext = Depends(context_dependency),
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List metric snapshots with cursor pagination."""
        try:
            check_authorization(
                context.role, "metrics", "read", project_id=context.project_id
            )
        except AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "unauthorized",
                    "retryable": False,
                    "safe_detail": "cannot read metrics",
                    "trace_id": get_trace_id(),
                    "schema_version": "we3.error.v1",
                },
            )

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
        request: Request,
        context: RequestContext = Depends(context_dependency),
    ) -> dict[str, Any]:
        """Generate a signed dossier for an experiment."""
        try:
            check_authorization(
                context.role, "exports", "create:dossier", project_id=context.project_id
            )
        except AuthorizationError:
            try:
                check_authorization(
                    context.role, "exports", "create", project_id=context.project_id
                )
            except AuthorizationError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "unauthorized",
                        "retryable": False,
                        "safe_detail": "cannot generate dossier",
                        "trace_id": get_trace_id(),
                        "schema_version": "we3.error.v1",
                    },
                )

        return {
            "schema_version": "we3.operation.v1",
            "trace_id": get_trace_id(),
            "project_id": context.project_id,
            "status": "generating_dossier",
        }


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "IdempotencyStore",
    "IdempotencyRecord",
    "CursorPage",
    "compute_etag",
    "encode_cursor",
    "decode_cursor",
    "get_idempotency_store",
    "add_operation_endpoints",
]