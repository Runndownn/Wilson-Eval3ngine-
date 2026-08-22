"""Request-scoped durable authorization-decision auditing.

The core authorization matrix remains usable without a web framework. Supported
API composition wraps each request in an ``authorization_audit_scope`` whose
callback writes the exact allow/deny decision to the hash-linked audit ledger.
A required audit write occurs synchronously before ``check_authorization``
returns an allow decision, so a protected side effect cannot proceed after an
auditable-decision persistence failure.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..security.authorization import (
    AuthorizationAuditUnavailable,
    authorization_audit_scope,
)

logger = logging.getLogger("wilson.api.authorization_audit")


class AuthorizationAuditMiddleware(BaseHTTPMiddleware):
    """Bind durable audit persistence to API authorization checks."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        def record_decision(
            role: str,
            resource: str,
            action: str,
            allowed: bool,
            project_id: str | None,
        ) -> None:
            context = getattr(request.state, "we3_context", None)
            ledger = getattr(request.app.state, "audit_ledger", None)
            if context is None or ledger is None:
                raise AuthorizationAuditUnavailable(
                    "request identity/audit authority is unavailable"
                )

            # The authenticated context is authoritative. A caller-provided
            # project argument may only agree with it; it can never select a
            # different audit tenant.
            if project_id is not None and project_id != context.project_id:
                raise AuthorizationAuditUnavailable(
                    "authorization project scope disagrees with authenticated context"
                )

            try:
                ledger.append(
                    project_id=context.project_id,
                    event_type=(
                        "api_authorization_allowed"
                        if allowed
                        else "api_authorization_denied"
                    ),
                    aggregate_type="authorization",
                    aggregate_id=resource,
                    actor_id=context.actor_id
                    or f"{context.auth_method}:{context.role}",
                    payload={
                        "role": role,
                        "resource": resource,
                        "action": action,
                        "allowed": allowed,
                        "method": request.method,
                    },
                )
            except AuthorizationAuditUnavailable:
                raise
            except Exception as exc:
                logger.error(
                    "authorization_audit_persistence_failed",
                    extra={
                        "error_class": type(exc).__name__,
                        "resource": resource,
                        "action": action,
                    },
                )
                raise AuthorizationAuditUnavailable(
                    "authorization decision audit is unavailable"
                ) from exc

        try:
            with authorization_audit_scope(record_decision):
                return await call_next(request)
        except AuthorizationAuditUnavailable as exc:
            logger.error(
                "authorization_audit_unavailable",
                extra={"error_class": type(exc).__name__},
            )
            return JSONResponse(
                status_code=503,
                headers={"Cache-Control": "no-store", "Retry-After": "1"},
                content={
                    "schema_version": "we3.error.v1",
                    "code": "audit_unavailable",
                    "retryable": True,
                    "safe_detail": "security audit persistence is unavailable",
                },
            )


__all__ = ["AuthorizationAuditMiddleware"]
