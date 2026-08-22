"""Hardened request-boundary middleware composition.

This module owns controls whose security properties depend on deployment trust:
CORS origin enforcement and distributed rate limiting.  It composes the
existing logging, tracing, content-type, CSRF, header, health, and streaming
body-limit controls without duplicating their implementation.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Iterable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _environment() -> str:
    return os.environ.get("WE3_ENVIRONMENT", "development").strip().lower()


def _is_assurance_environment() -> bool:
    return _environment() in {"staging", "production"}


def _merge_vary(response: Response, token: str) -> None:
    current = [part.strip() for part in response.headers.get("Vary", "").split(",")]
    values = {part for part in current if part}
    values.add(token)
    response.headers["Vary"] = ", ".join(sorted(values))


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """Enforce an exact browser-origin policy before route side effects.

    CORS is not an authentication mechanism and does not replace CSRF controls.
    The purpose of this middleware is narrower: when a browser supplies an
    ``Origin`` header, an unauthorized origin is rejected before the endpoint is
    called. Preflight method/header requests are validated rather than receiving
    a generic 204 response.
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
        origins = tuple(allowed_origins) if allowed_origins is not None else _csv(
            os.environ.get("WE3_CORS_ALLOWED_ORIGINS", "")
        )
        self._allowed_origins = frozenset(origins)
        self._allowed_methods = frozenset(
            method.upper()
            for method in (allowed_methods or legacy.CORS_ALLOWED_METHODS)
        )
        self._allowed_headers = frozenset(
            header.lower()
            for header in (allowed_headers or legacy.CORS_ALLOWED_HEADERS)
        )
        self._allow_credentials = allow_credentials
        self._max_age = max_age

        if "*" in self._allowed_origins:
            raise ValueError("wildcard CORS origins are not permitted")
        if allow_credentials and "*" in self._allowed_headers:
            raise ValueError("wildcard CORS headers are not permitted with credentials")

    @staticmethod
    def _deny(code: str, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "schema_version": "we3.error.v1",
                "code": code,
                "retryable": False,
                "safe_detail": detail,
            },
            headers={"Cache-Control": "no-store", "Vary": "Origin"},
        )

    def _origin_allowed(self, origin: str | None) -> bool:
        return origin is None or origin in self._allowed_origins

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
            return self._deny("origin_not_allowed", "request origin is not allowed")

        if request.method == "OPTIONS" and request.headers.get(
            "Access-Control-Request-Method"
        ):
            requested_method = request.headers.get(
                "Access-Control-Request-Method", ""
            ).upper()
            if requested_method not in self._allowed_methods:
                return self._deny(
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
                return self._deny(
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
    ) -> None:
        super().__init__(app)
        fail_closed = _is_assurance_environment()
        trusted_proxy_cidrs = _csv(
            os.environ.get("WE3_TRUSTED_PROXY_CIDRS", "")
        )

        # Registering a Lua script is lazy in redis-py. An explicit ping is the
        # startup proof that an assurance deployment can reach its distributed
        # security-state authority.
        if fail_closed:
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
            fail_closed=fail_closed,
            trusted_proxy_cidrs=trusted_proxy_cidrs,
        )
        self._default_limit = default_limit
        self._window_seconds = default_window

    @staticmethod
    def _unavailable() -> JSONResponse:
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

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        identity = self._limiter.resolve_client_identity(request)
        path = request.url.path
        config = legacy.RATE_LIMIT_RULES.get(
            path, RateLimitConfig(self._default_limit)
        )
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
            return self._unavailable()

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


def add_hardened_production_middleware(
    app: FastAPI,
    database_url: str,
    artifact_root: str,
    auth_mode: str,
    redis_client: Any | None = None,
) -> None:
    """Compose the supported request security boundary.

    Starlette executes middleware in reverse registration order. Structured
    logging remains outermost; the streamed-byte limiter is innermost and wraps
    body consumption before framework parsing reaches endpoints.
    """
    legacy.register_default_health_checks(database_url, artifact_root, auth_mode)

    app.add_middleware(StreamingBodyLimitMiddleware)
    app.add_middleware(legacy.CSRFProtectionMiddleware, auth_mode=auth_mode)
    app.add_middleware(legacy.ContentTypeValidationMiddleware)
    app.add_middleware(StrictCORSMiddleware)
    app.add_middleware(
        AuthoritativeRateLimitMiddleware,
        redis_client=redis_client,
        default_limit=legacy.RATE_LIMIT_DEFAULT,
        default_window=60,
    )
    app.add_middleware(legacy.SecurityHeadersMiddleware)
    app.add_middleware(legacy.TracingMiddleware)
    app.add_middleware(legacy.StructuredLoggingMiddleware)


__all__ = [
    "AuthoritativeRateLimitMiddleware",
    "StrictCORSMiddleware",
    "add_hardened_production_middleware",
]
