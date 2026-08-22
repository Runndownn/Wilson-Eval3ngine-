"""Hardened request-boundary middleware and identity composition.

Security properties that depend on deployment trust are bound here instead of
being inferred later inside route code. The registrar captures secret/trust
configuration while the application is composed, installs one OIDC authenticator
shared by the API, and then wires request controls around the route layer.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Awaitable, Callable, Iterable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..persistence.audit import AuditLedger
from ..security.csrf import CSRFProtection, CSRFValidationError
from ..security.input_validation import (
    IdempotencyKeyValidator,
    ProjectIdValidator,
    ValidationError,
)
from ..security.oidc import (
    OIDCAuthenticator,
    OIDCSettings,
    TokenRevocationError,
    TokenValidationError,
)
from ..security.rate_limit import (
    RateLimitBackendUnavailable,
    RateLimitConfig,
    RateLimiter,
    build_rate_limit_key,
)
from ..telemetry import get_correlation_context
from .body_limit import StreamingBodyLimitMiddleware
from . import middleware as legacy

logger = logging.getLogger("wilson.api.security_middleware")
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _merge_vary(response: Response, token: str) -> None:
    current = [part.strip() for part in response.headers.get("Vary", "").split(",")]
    values = {part for part in current if part}
    values.add(token)
    response.headers["Vary"] = ", ".join(sorted(values))


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "schema_version": "we3.error.v1",
            "code": code,
            "retryable": status_code >= 500,
            "safe_detail": detail,
        },
        headers={"Cache-Control": "no-store"},
    )


class RequestMetadataValidationMiddleware(BaseHTTPMiddleware):
    """Reject malformed security metadata before it reaches route code."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id is not None and not _CORRELATION_ID.fullmatch(correlation_id):
            return _error(400, "invalid_correlation_id", "correlation identifier is invalid")

        project_id = request.headers.get("X-WE3-Project-ID")
        if project_id is not None:
            try:
                ProjectIdValidator.validate(project_id)
            except ValidationError:
                return _error(400, "invalid_project_id", "project identifier is invalid")

        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key is not None:
            try:
                IdempotencyKeyValidator.validate(idempotency_key)
            except ValidationError:
                return _error(400, "invalid_idempotency_key", "idempotency key is invalid")

        return await call_next(request)


class BoundCSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF validation whose HMAC key is captured during app composition.

    Current production authentication is bearer-header OIDC, which is not an
    ambient browser credential and is therefore exempt. If a future route uses
    cookie/session credentials, state-changing requests must present the same
    HMAC token in the cookie and ``X-CSRF-Token`` header.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        auth_mode: str,
        csrf_secret: str,
        assurance_environment: bool,
    ) -> None:
        super().__init__(app)
        self._auth_mode = auth_mode
        if assurance_environment and not csrf_secret:
            raise ValueError("CSRF secret is required in staging/production")
        self._csrf = CSRFProtection(secret=csrf_secret or None)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method not in _STATE_CHANGING_METHODS:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if self._auth_mode == "oidc" and authorization.startswith("Bearer "):
            return await call_next(request)
        if self._auth_mode == "dev":
            return await call_next(request)

        header_token = request.headers.get("X-CSRF-Token", "")
        cookie_token = request.cookies.get("csrf_token", "")
        if not header_token or not cookie_token:
            return _error(
                403,
                "csrf_token_missing",
                "request verification token is required",
            )
        try:
            self._csrf.validate_token(header_token, cookie_token)
        except CSRFValidationError:
            return _error(
                403,
                "csrf_token_invalid",
                "request verification token is invalid",
            )
        return await call_next(request)


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """Enforce an exact browser-origin policy before route side effects.

    CORS is not authentication and is not a substitute for CSRF. Its job here is
    to reject an unauthorized browser ``Origin`` before endpoint execution and
    to validate preflight method/header requests instead of acknowledging every
    preflight with a generic success response.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: Iterable[str] | None = None,
        allowed_methods: Iterable[str] | None = None,
        allowed_headers: Iterable[str] | None = None,
        allow_credentials: bool = True,
        max_age: int = legacy.CORS_MAX_AGE,
    ) -> None:
        super().__init__(app)
        self._allowed_origins = frozenset(allowed_origins or ())
        self._allowed_methods = frozenset(
            method.upper() for method in (allowed_methods or legacy.CORS_ALLOWED_METHODS)
        )
        self._allowed_headers = frozenset(
            header.lower() for header in (allowed_headers or legacy.CORS_ALLOWED_HEADERS)
        )
        self._allow_credentials = allow_credentials
        self._max_age = max_age
        if "*" in self._allowed_origins:
            raise ValueError("wildcard CORS origins are not permitted")
        if allow_credentials and "*" in self._allowed_headers:
            raise ValueError("wildcard CORS headers are not permitted with credentials")

    def _apply_headers(self, response: Response, origin: str) -> None:
        response.headers["Access-Control-Allow-Origin"] = origin
        if self._allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        _merge_vary(response, "Origin")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        origin = request.headers.get("Origin")
        if origin is not None and origin not in self._allowed_origins:
            logger.warning("cors_origin_rejected")
            response = _error(403, "origin_not_allowed", "request origin is not allowed")
            _merge_vary(response, "Origin")
            return response

        if request.method == "OPTIONS" and request.headers.get(
            "Access-Control-Request-Method"
        ):
            requested_method = request.headers.get(
                "Access-Control-Request-Method", ""
            ).upper()
            if requested_method not in self._allowed_methods:
                return _error(
                    403,
                    "cors_method_not_allowed",
                    "requested cross-origin method is not allowed",
                )

            requested_headers = {
                item.strip().lower()
                for item in request.headers.get(
                    "Access-Control-Request-Headers", ""
                ).split(",")
                if item.strip()
            }
            if not requested_headers.issubset(self._allowed_headers):
                return _error(
                    403,
                    "cors_headers_not_allowed",
                    "requested cross-origin headers are not allowed",
                )

            response = Response(status_code=204)
            if origin is not None:
                self._apply_headers(response, origin)
            response.headers["Access-Control-Allow-Methods"] = ", ".join(
                sorted(self._allowed_methods)
            )
            response.headers["Access-Control-Allow-Headers"] = ", ".join(
                sorted(self._allowed_headers)
            )
            response.headers["Access-Control-Max-Age"] = str(self._max_age)
            return response

        response = await call_next(request)
        if origin is not None:
            self._apply_headers(response, origin)
        return response


class AuthoritativeRateLimitMiddleware(BaseHTTPMiddleware):
    """Distributed rate limiting with explicit failure and proxy trust policy."""

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
        default_limit: int = legacy.RATE_LIMIT_DEFAULT,
        default_window: int = 60,
        *,
        trusted_proxy_cidrs: Iterable[str] = (),
        assurance_environment: bool = False,
    ) -> None:
        super().__init__(app)
        if assurance_environment:
            if redis_client is None:
                raise RateLimitBackendUnavailable(
                    "Redis is required for production rate limiting"
                )
            try:
                redis_client.ping()
            except Exception as exc:
                raise RateLimitBackendUnavailable(
                    "Redis rate-limit authority is unavailable at startup"
                ) from exc

        self._limiter = RateLimiter(
            redis_client=redis_client,
            default_limit=default_limit,
            default_window=default_window,
            fail_closed=assurance_environment,
            trusted_proxy_cidrs=trusted_proxy_cidrs,
        )
        self._default_limit = default_limit
        self._window_seconds = default_window

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        identity = self._limiter.resolve_client_identity(request)
        path = request.url.path
        config = legacy.RATE_LIMIT_RULES.get(path, RateLimitConfig(self._default_limit))
        effective_limit = config.effective_limit()
        key = build_rate_limit_key(identity.enforcement_token, path)

        try:
            result = self._limiter.check(
                key,
                limit=effective_limit,
                window_seconds=self._window_seconds,
            )
        except RateLimitBackendUnavailable:
            logger.error(
                "rate_limit_backend_unavailable",
                extra={"client_ip": identity.log_label, "path": path},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "schema_version": "we3.error.v1",
                    "code": "rate_limit_backend_unavailable",
                    "retryable": True,
                    "safe_detail": "request rate authority is unavailable",
                },
                headers={"Cache-Control": "no-store", "Retry-After": "1"},
            )

        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "structured": {
                        "event": "rate_limit_exceeded",
                        "client_ip": identity.log_label,
                        "path": path,
                        "limit": effective_limit,
                        "retry_after": result.retry_after,
                        "backend": result.backend,
                    }
                },
            )
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(effective_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(result.reset_at)),
                },
                content={
                    "schema_version": "we3.error.v1",
                    "code": "rate_limit_exceeded",
                    "retryable": True,
                    "safe_detail": "rate limit exceeded",
                    "trace_id": get_correlation_context().trace_id,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(effective_limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at))
        return response


def _install_oidc_authority(app: FastAPI, redis_client: Any | None) -> None:
    runtime = app.state.settings
    if runtime.auth_mode != "oidc":
        return

    authenticator = OIDCAuthenticator(
        OIDCSettings(
            issuer=runtime.oidc_issuer,
            jwks_uri=runtime.oidc_jwks_uri,
            audience=runtime.oidc_audience,
        ),
        redis_client=redis_client,
    )
    app.state.oidc_authenticator = authenticator
    app.state.audit_ledger = AuditLedger(app.state.database)

    @app.post("/v1/auth/revoke", status_code=204, include_in_schema=True)
    def revoke_current_bearer(request: Request) -> Response:
        """Revoke the currently presented bearer token for its remaining life.

        This is intentionally self-revocation. Administrative revocation by
        subject/session belongs to the identity provider or a separately
        authorized security-administration API.
        """
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return _error(401, "missing_bearer_token", "authorization header required")
        token = authorization[7:]
        if not token or len(token) > 16_384:
            return _error(401, "invalid_token", "token validation failed")

        try:
            project_id, role, actor_id = authenticator.authenticate_context(token)
        except TokenRevocationError:
            # Revocation is idempotent and should not reveal prior revocation
            # timing/state to a caller that already possesses the token value.
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
        except TokenValidationError:
            return _error(401, "invalid_token", "token validation failed")
        except Exception as exc:
            logger.error(
                "token_revoke_authentication_unavailable",
                extra={"error_class": type(exc).__name__},
            )
            return _error(503, "oidc_unavailable", "authentication service is unavailable")

        if not authenticator.revoke_token(token):
            return _error(503, "revocation_failed", "token revocation could not be completed")

        try:
            app.state.audit_ledger.append(
                project_id=ProjectIdValidator.validate(project_id),
                event_type="oidc_token_self_revoked",
                aggregate_type="identity",
                aggregate_id=actor_id,
                actor_id=actor_id,
                payload={"role": role, "auth_method": "oidc"},
            )
        except Exception as exc:
            logger.error(
                "token_revocation_audit_failed",
                extra={"error_class": type(exc).__name__},
            )
            # The security action already succeeded. Report that evidence
            # persistence is unavailable without attempting to undo revocation.
            return _error(503, "audit_unavailable", "security audit persistence is unavailable")

        return Response(status_code=204, headers={"Cache-Control": "no-store"})


def add_hardened_production_middleware(
    app: FastAPI,
    database_url: str,
    artifact_root: str,
    auth_mode: str,
    redis_client: Any | None = None,
) -> None:
    """Compose the supported identity and request security boundary."""
    legacy.register_default_health_checks(database_url, artifact_root, auth_mode)
    runtime = app.state.settings
    assurance = bool(runtime.is_assurance_environment)

    # Use captured Settings values rather than re-reading mutable environment
    # state after the external secret lease has been released.
    csrf_secret = runtime.csrf_secret
    allowed_origins = runtime.cors_allowed_origins
    trusted_proxy_cidrs = runtime.trusted_proxy_cidrs

    _install_oidc_authority(app, redis_client)

    app.add_middleware(StreamingBodyLimitMiddleware)
    app.add_middleware(
        BoundCSRFProtectionMiddleware,
        auth_mode=auth_mode,
        csrf_secret=csrf_secret,
        assurance_environment=assurance,
    )
    app.add_middleware(legacy.ContentTypeValidationMiddleware)
    app.add_middleware(RequestMetadataValidationMiddleware)
    app.add_middleware(StrictCORSMiddleware, allowed_origins=allowed_origins)
    app.add_middleware(
        AuthoritativeRateLimitMiddleware,
        redis_client=redis_client,
        default_limit=legacy.RATE_LIMIT_DEFAULT,
        default_window=60,
        trusted_proxy_cidrs=trusted_proxy_cidrs,
        assurance_environment=assurance,
    )
    app.add_middleware(legacy.SecurityHeadersMiddleware)
    app.add_middleware(legacy.TracingMiddleware)
    app.add_middleware(legacy.StructuredLoggingMiddleware)


__all__ = [
    "AuthoritativeRateLimitMiddleware",
    "BoundCSRFProtectionMiddleware",
    "RequestMetadataValidationMiddleware",
    "StrictCORSMiddleware",
    "add_hardened_production_middleware",
]
