"""Authoritative HTTP security boundaries for the production API.

This module replaces the early foundation middleware implementations at package
composition time.  The legacy classes remain import-compatible for historical
callers, while supported API entrypoints receive these stricter invariants:

* distributed rate limiting fails closed in staging/production;
* forwarding headers are trusted only from explicitly configured proxy CIDRs;
* caller-controlled project headers never select a pre-authentication bucket;
* complete client addresses are used only to derive one-way enforcement keys;
* logs receive only an anonymized client label; and
* disallowed CORS origins/preflights are rejected by the server, not merely left
  for a browser to ignore.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
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

logger = logging.getLogger("wilson.api.security_boundary")

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_DEFAULT_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
_DEFAULT_HEADERS = frozenset(
    {
        "authorization",
        "content-type",
        "x-csrf-token",
        "x-correlation-id",
        "x-we3-project-id",
        "idempotency-key",
        "if-match",
    }
)


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.environ.get(name, "").split(",")
        if item.strip()
    )


def _trace_id() -> str:
    try:
        return get_correlation_context().trace_id
    except Exception:
        return ""


class AuthoritativeRateLimitMiddleware(BaseHTTPMiddleware):
    """Pre-authentication abuse control with explicit distributed authority."""

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
        default_limit: int = 1000,
        default_window: int = 60,
    ) -> None:
        super().__init__(app)
        environment = os.environ.get("WE3_ENVIRONMENT", "development").strip().lower()
        self._fail_closed = environment in {"production", "staging"}
        self._limiter = RateLimiter(
            redis_client=redis_client,
            default_limit=default_limit,
            default_window=default_window,
            fail_closed=self._fail_closed,
            trusted_proxy_cidrs=_csv_env("WE3_TRUSTED_PROXY_CIDRS"),
        )
        self._window_seconds = default_window
        self._default_limit = default_limit

    @staticmethod
    def _rules() -> dict[str, RateLimitConfig]:
        # Resolve dynamically so tests and operator configuration can change the
        # canonical middleware rules without duplicating them here.
        from . import middleware as legacy  # noqa: PLC0415

        return legacy.RATE_LIMIT_RULES

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        identity = self._limiter.resolve_client_identity(request)
        path = request.url.path
        config = self._rules().get(path, RateLimitConfig(self._default_limit))
        limit = config.effective_limit()
        key = build_rate_limit_key(identity.address, path)

        try:
            result = self._limiter.check(
                key,
                limit=limit,
                window_seconds=self._window_seconds,
            )
        except RateLimitBackendUnavailable:
            logger.error(
                "authoritative_rate_limit_unavailable",
                extra={
                    "structured": {
                        "event": "rate_limit_backend_unavailable",
                        "client_ip": identity.log_label,
                        "path": path,
                    }
                },
            )
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
                content={
                    "schema_version": "we3.error.v1",
                    "code": "rate_limit_backend_unavailable",
                    "retryable": True,
                    "safe_detail": "request admission service unavailable",
                    "trace_id": _trace_id(),
                },
            )

        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "structured": {
                        "event": "rate_limit_exceeded",
                        "client_ip": identity.log_label,
                        "path": path,
                        "limit": limit,
                        "retry_after": result.retry_after,
                        "backend": result.backend,
                    }
                },
            )
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(result.reset_at)),
                    "Cache-Control": "no-store",
                },
                content={
                    "schema_version": "we3.error.v1",
                    "code": "rate_limit_exceeded",
                    "retryable": True,
                    "safe_detail": "rate limit exceeded",
                    "trace_id": _trace_id(),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at))
        return response


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """Explicit CORS allowlist with server-side rejection.

    CORS is not an authentication mechanism.  This boundary only constrains
    browser-originated cross-origin traffic; OIDC/RBAC remains authoritative.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: list[str] | None = None,
        allowed_methods: list[str] | None = None,
        allowed_headers: list[str] | None = None,
        allow_credentials: bool = True,
        max_age: int = 3600,
    ) -> None:
        super().__init__(app)
        configured_origins = allowed_origins
        if configured_origins is None:
            configured_origins = list(_csv_env("WE3_CORS_ALLOWED_ORIGINS"))
            if not configured_origins:
                configured_origins = ["https://eval3ngine.local"]
        self._allowed_origins = frozenset(
            origin.strip().rstrip("/")
            for origin in configured_origins
            if origin.strip()
        )
        if "*" in self._allowed_origins:
            raise ValueError("wildcard CORS origins are not supported")

        self._allowed_methods = frozenset(
            method.upper() for method in (allowed_methods or _DEFAULT_METHODS)
        )
        self._allowed_headers = frozenset(
            header.lower() for header in (allowed_headers or _DEFAULT_HEADERS)
        )
        self._allow_credentials = bool(allow_credentials)
        self._max_age = max(0, int(max_age))

    @staticmethod
    def _deny(code: str, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            headers={"Cache-Control": "no-store", "Vary": "Origin"},
            content={
                "schema_version": "we3.error.v1",
                "code": code,
                "retryable": False,
                "safe_detail": detail,
                "trace_id": _trace_id(),
            },
        )

    def _origin_allowed(self, origin: str) -> bool:
        normalized = origin.strip().rstrip("/")
        return normalized in self._allowed_origins

    def _apply_simple_headers(self, response: Response, origin: str) -> None:
        response.headers["Access-Control-Allow-Origin"] = origin.strip().rstrip("/")
        if self._allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        existing_vary = response.headers.get("Vary", "")
        vary_values = {item.strip() for item in existing_vary.split(",") if item.strip()}
        vary_values.add("Origin")
        response.headers["Vary"] = ", ".join(sorted(vary_values))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        origin = request.headers.get("Origin")
        if origin is None:
            return await call_next(request)

        if not self._origin_allowed(origin):
            logger.warning("cors_origin_rejected", extra={"origin_rejected": True})
            return self._deny("cors_origin_denied", "origin is not allowed")

        if request.method == "OPTIONS" and request.headers.get(
            "Access-Control-Request-Method"
        ):
            requested_method = request.headers["Access-Control-Request-Method"].upper()
            if requested_method not in self._allowed_methods:
                return self._deny("cors_method_denied", "requested method is not allowed")

            requested_headers = {
                header.strip().lower()
                for header in request.headers.get(
                    "Access-Control-Request-Headers", ""
                ).split(",")
                if header.strip()
            }
            if not requested_headers.issubset(self._allowed_headers):
                return self._deny("cors_headers_denied", "requested headers are not allowed")

            response = Response(status_code=204)
            self._apply_simple_headers(response, origin)
            response.headers["Access-Control-Allow-Methods"] = ", ".join(
                sorted(self._allowed_methods)
            )
            response.headers["Access-Control-Allow-Headers"] = ", ".join(
                sorted(self._allowed_headers)
            )
            response.headers["Access-Control-Max-Age"] = str(self._max_age)
            response.headers["Cache-Control"] = "no-store"
            return response

        response = await call_next(request)
        self._apply_simple_headers(response, origin)
        return response


__all__ = ["AuthoritativeRateLimitMiddleware", "StrictCORSMiddleware"]
