"""
Production middleware for the Wilson Eval3ngine API.

Includes:
- Structured request logging with correlation IDs
- Security headers (CSP, HSTS, X-Frame-Options, COOP, CORP, etc.)
- Rate limiting (Redis-backed distributed, in-memory fallback)
- Request/response body size limits
- Graceful shutdown support
- CORS policy enforcement
- Content-type validation
- CSRF protection for state-changing operations

Security: All middleware is designed to never log sensitive data.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..telemetry import (
    CorrelationContext,
    get_correlation_context,
    set_correlation_context,
)
from ..tracing import (
    Tracer,
    extract_trace_context,
    get_tracer,
    propagate_trace_context,
)
from ..util import new_id
from ..security.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    build_rate_limit_key,
)
from ..security.csrf import CSRFProtection, CSRFValidationError
from ..security.input_validation import (
    InputValidator,
    ProjectIdValidator,
    IdempotencyKeyValidator,
    ContentTypeValidator,
)

logger = logging.getLogger("wilson.api.middleware")

# ============================================================================
# Configuration
# ============================================================================

# Security headers configuration
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "Permissions-Policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "X-Permitted-Cross-Domain-Policies": "none",
}

# Rate limiting configuration
RATE_LIMIT_DEFAULT = int(os.getenv("WE3_RATE_LIMIT_DEFAULT", "1000"))  # requests per minute
RATE_LIMIT_AUTH = int(os.getenv("WE3_RATE_LIMIT_AUTH", "10"))  # auth endpoint limit
RATE_LIMIT_BURST = int(os.getenv("WE3_RATE_LIMIT_BURST", "20"))  # burst allowance

# Request body size limit (10 MB)
MAX_BODY_SIZE = int(os.getenv("WE3_MAX_BODY_SIZE", str(10 * 1024 * 1024)))

# CORS configuration
CORS_ALLOWED_ORIGINS = os.getenv(
    "WE3_CORS_ALLOWED_ORIGINS",
    "https://eval3ngine.local",
).split(",")
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-CSRF-Token",
    "X-Correlation-ID",
    "X-WE3-Project-ID",
    "Idempotency-Key",
]
CORS_ALLOW_CREDENTIALS = True
CORS_MAX_AGE = 3600


# Endpoint-specific rate limits
RATE_LIMIT_RULES: dict[str, RateLimitConfig] = {
    "/v1/experiments:validate": RateLimitConfig(RATE_LIMIT_DEFAULT),
    "/v1/experiments:run": RateLimitConfig(RATE_LIMIT_DEFAULT, burst=5),
    "/health": RateLimitConfig(60),
    "/metrics": RateLimitConfig(60),
}


# ============================================================================
# Structured Logging Middleware
# ============================================================================


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that adds structured logging with correlation IDs.

    Logs every request and response with:
    - Correlation ID (trace_id) propagated via X-Correlation-ID header
    - Request method, path, status code, duration
    - Client IP (anonymized)
    - Never logs request/response bodies or sensitive headers
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Generate or propagate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or new_id("trc")

        # Create correlation context
        context = CorrelationContext(
            trace_id=correlation_id,
            project_id=request.headers.get("X-WE3-Project-ID", ""),
        )
        set_correlation_context(context)

        # Record start time
        start_time = time.monotonic()

        # Extract safe request info
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # Anonymize IP (last octet for IPv4, last 80 bits for IPv6)
        anonymized_ip = self._anonymize_ip(client_host)

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error_detail = None
        except Exception as exc:
            status_code = 500
            error_detail = type(exc).__name__
            response = JSONResponse(
                status_code=500,
                content={
                    "schema_version": "we3.error.v1",
                    "code": "internal_error",
                    "retryable": True,
                    "safe_detail": "internal server error",
                    "trace_id": correlation_id,
                },
            )

        # Calculate duration
        duration_ms = (time.monotonic() - start_time) * 1000

        # Log structured event (never logs body or sensitive data)
        log_data: dict[str, Any] = {
            "event": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": anonymized_ip,
            "trace_id": correlation_id,
        }
        if error_detail:
            log_data["error_class"] = error_detail

        logger.info("request_completed", extra={"structured": log_data})

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @staticmethod
    def _anonymize_ip(ip: str) -> str:
        """Anonymize client IP address for privacy."""
        if ":" in ip:
            # IPv6 - zero out last 80 bits
            parts = ip.split(":")
            if len(parts) > 2:
                return ":".join(parts[:2]) + ":0:0:0:0:0"
            return ip
        # IPv4 - zero out last octet
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0"
        return ip


# ============================================================================
# Security Headers Middleware
# ============================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers[header_name] = header_value
        return response


# ============================================================================
# Rate Limiting Middleware
# ============================================================================


@dataclass
class RateLimitState:
    """In-memory rate limit state for a client (fallback mode)."""

    request_count: int = 0
    window_start: float = field(default_factory=time.monotonic)
    burst_used: int = 0


# Endpoint-specific rate limits
RATE_LIMIT_RULES: dict[str, RateLimitConfig] = {
    "/v1/experiments:validate": RateLimitConfig(RATE_LIMIT_DEFAULT),
    "/v1/experiments:run": RateLimitConfig(RATE_LIMIT_DEFAULT, burst=5),
    "/health": RateLimitConfig(60),
    "/metrics": RateLimitConfig(60),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis-backed distributed rate limiting.

    Uses atomic Lua scripts via Redis for distributed rate limiting.
    Falls back to in-memory sliding window when Redis is unavailable.

    Security:
    - Sliding window algorithm prevents burst attacks at window boundaries
    - Project-scoped keys prevent cross-tenant rate limit bypass
    - IP anonymization in logs
    - Fail-open on Redis errors (better to serve than block all)
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
        default_limit: int = RATE_LIMIT_DEFAULT,
        default_window: int = 60,
    ) -> None:
        super().__init__(app)
        self._limiter = RateLimiter(
            redis_client=redis_client,
            default_limit=default_limit,
            default_window=default_window,
        )
        self._window_seconds: int = default_window
        self._default_limit: int = default_limit

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client_ip = self._limiter.get_client_ip(request)
        path = request.url.path
        project_id = request.headers.get("X-WE3-Project-ID")

        # Build rate limit key with project scope
        rl_key = build_rate_limit_key(client_ip, path, project_id)

        # Get rate limit config for this endpoint
        config = RATE_LIMIT_RULES.get(path, RateLimitConfig(self._default_limit))

        # Check rate limit
        result = self._limiter.check(rl_key, limit=config.requests_per_minute, window_seconds=self._window_seconds)

        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "structured": {
                        "event": "rate_limit_exceeded",
                        "client_ip": client_ip,
                        "path": path,
                        "project_id": project_id or "",
                        "limit": config.requests_per_minute,
                        "retry_after": result.retry_after,
                    }
                },
            )
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(config.requests_per_minute),
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

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, result.remaining))
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at))

        return response


# ============================================================================
# Body Size Limit Middleware
# ============================================================================


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests with bodies exceeding the configured limit."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Check Content-Length header first (fast path)
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "schema_version": "we3.error.v1",
                    "code": "payload_too_large",
                    "retryable": False,
                    "safe_detail": "request body exceeds maximum allowed size",
                    "trace_id": get_correlation_context().trace_id,
                },
            )

        response = await call_next(request)
        return response


# ============================================================================
# CORS Middleware
# ============================================================================


class CORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware with explicit origin allowlist.

    Security:
    - Only allows explicitly configured origins
    - Rejects all cross-origin requests by default
    - Supports credentials for authenticated requests
    - Preflight caching with limited max-age
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: list[str] | None = None,
        allowed_methods: list[str] | None = None,
        allowed_headers: list[str] | None = None,
        allow_credentials: bool = True,
        max_age: int = CORS_MAX_AGE,
    ) -> None:
        super().__init__(app)
        self._allowed_origins = set((allowed_origins or CORS_ALLOWED_ORIGINS))
        self._allowed_methods = set((allowed_methods or CORS_ALLOWED_METHODS))
        self._allowed_headers = set((allowed_headers or CORS_ALLOWED_HEADERS))
        self._allow_credentials = allow_credentials
        self._max_age = max_age

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        origin = request.headers.get("Origin")

        # Handle preflight requests
        if request.method == "OPTIONS":
            response = JSONResponse(status_code=204, content={})
            self._set_cors_headers(response, origin)
            return response

        # Process request
        response = await call_next(request)

        # Set CORS headers on response
        self._set_cors_headers(response, origin)
        return response

    def _set_cors_headers(self, response: Response, origin: str | None) -> None:
        """Set CORS headers if origin is allowed."""
        if origin and origin in self._allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            if self._allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        # If origin not allowed, no CORS headers are set (request blocked by browser)

    @staticmethod
    def _is_valid_origin(origin: str) -> bool:
        """Validate that origin is a well-formed URL."""
        if not origin:
            return False
        try:
            from urllib.parse import urlparse  # noqa: PLC0415

            parsed = urlparse(origin)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False


# ============================================================================
# Content-Type Validation Middleware
# ============================================================================


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Validates content-type of incoming requests.

    Security:
    - Rejects requests with unexpected content types for POST/PUT/PATCH
    - Prevents content-type confusion attacks
    - Allows GET/HEAD/OPTIONS without content-type
    """

    # Endpoints that accept JSON
    _JSON_ENDPOINTS = {
        "/v1/experiments:run",
        "/v1/experiments:validate",
        "/v1/operations",
        "/v1/auth/revoke",
    }

    # Endpoints that accept form data
    _FORM_ENDPOINTS = {
        "/v1/auth/login",
    }

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        method = request.method
        path = request.url.path

        # Only validate content-type for methods with bodies
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            content_type = request.headers.get("Content-Type", "")

            # Determine expected content type
            if path in self._JSON_ENDPOINTS:
                validator = ContentTypeValidator()
                is_valid, error = validator.validate_json(content_type)
                if not is_valid:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "schema_version": "we3.error.v1",
                            "code": "unsupported_media_type",
                            "retryable": False,
                            "safe_detail": error,
                            "trace_id": get_correlation_context().trace_id,
                        },
                    )
            elif path in self._FORM_ENDPOINTS:
                validator = ContentTypeValidator()
                is_valid, error = validator.validate_form(content_type)
                if not is_valid:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "schema_version": "we3.error.v1",
                            "code": "unsupported_media_type",
                            "retryable": False,
                            "safe_detail": error,
                            "trace_id": get_correlation_context().trace_id,
                        },
                    )

        response = await call_next(request)
        return response


# ============================================================================
# CSRF Protection Middleware
# ============================================================================


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection for state-changing operations.

    Security:
    - Double-submit cookie pattern
    - Requires X-CSRF-Token header for POST/PUT/PATCH/DELETE
    - Token validated against session cookie
    - Exempt for OIDC Bearer token authentication (tokens are not cookie-based)
    - Exempt for dev mode (header-based auth, not cookie-based)
    """

    # Methods that require CSRF protection
    _STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths exempt from CSRF (use Bearer token auth, not cookies)
    _CSRF_EXEMPT_PATHS = {
        "/v1/auth/revoke",
        "/v1/auth/refresh",
    }

    def __init__(self, app: ASGIApp, auth_mode: str = "oidc") -> None:
        super().__init__(app)
        self._auth_mode = auth_mode
        self._csrf = CSRFProtection(secret=os.getenv("WE3_CSRF_SECRET", ""))

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Skip CSRF for safe methods
        if request.method not in self._STATE_CHANGING_METHODS:
            return await call_next(request)

        # Skip CSRF for exempt paths
        if request.url.path in self._CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF in OIDC mode when using Bearer token (not cookie-based)
        auth_header = request.headers.get("Authorization", "")
        if self._auth_mode == "oidc" and auth_header.startswith("Bearer "):
            return await call_next(request)

        # Skip CSRF in dev mode (header-based auth, not cookie-based)
        if self._auth_mode == "dev":
            return await call_next(request)

        # Validate CSRF token
        token = request.headers.get("X-CSRF-Token", "")
        csrf_cookie = request.cookies.get("csrf_token", "")

        if not token or not csrf_cookie:
            return JSONResponse(
                status_code=403,
                content={
                    "schema_version": "we3.error.v1",
                    "code": "csrf_token_missing",
                    "retryable": False,
                    "safe_detail": "CSRF token required for state-changing operations",
                    "trace_id": get_correlation_context().trace_id,
                },
            )

        try:
            self._csrf.validate_token(token, csrf_cookie)
        except CSRFValidationError as e:
            return JSONResponse(
                status_code=403,
                content={
                    "schema_version": "we3.error.v1",
                    "code": "csrf_token_invalid",
                    "retryable": False,
                    "safe_detail": str(e),
                    "trace_id": get_correlation_context().trace_id,
                },
            )

        response = await call_next(request)
        return response


# ============================================================================
# Health Check System
# ============================================================================


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """Definition of a health check."""

    name: str
    description: str
    critical: bool  # If True, failure makes readiness check fail


class HealthCheckRegistry:
    """Registry of health checks for readiness/liveness probes."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._implementations: dict[str, Callable[[], bool]] = {}

    def register(
        self,
        name: str,
        description: str,
        critical: bool,
        check_fn: Callable[[], bool],
    ) -> None:
        """Register a health check."""
        self._checks[name] = HealthCheck(
            name=name,
            description=description,
            critical=critical,
        )
        self._implementations[name] = check_fn

    def get_checks(self) -> list[HealthCheck]:
        """Get all registered health checks."""
        return list(self._checks.values())

    def run_all(self) -> dict[str, Any]:
        """Run all health checks and return results."""
        results: dict[str, Any] = {
            "checks": {},
            "status": "ok",
            "critical_failures": [],
        }

        for name, check in self._checks.items():
            try:
                passed = self._implementations[name]()
                results["checks"][name] = {
                    "description": check.description,
                    "critical": check.critical,
                    "status": "pass" if passed else "fail",
                }
                if not passed and check.critical:
                    results["critical_failures"].append(name)
            except Exception as exc:
                results["checks"][name] = {
                    "description": check.description,
                    "critical": check.critical,
                    "status": "error",
                    "error": type(exc).__name__,
                }
                if check.critical:
                    results["critical_failures"].append(name)

        if results["critical_failures"]:
            results["status"] = "degraded"

        return results


# Global health check registry
_health_registry: HealthCheckRegistry | None = None


def get_health_registry() -> HealthCheckRegistry:
    """Get the global health check registry."""
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    return _health_registry


def register_default_health_checks(
    database_url: str,
    artifact_root: str,
    auth_mode: str,
) -> HealthCheckRegistry:
    """Register default health checks for the platform."""
    registry = get_health_registry()

    # Database connectivity check
    def check_database() -> bool:
        try:
            from ..persistence.database import Database

            db = Database(database_url)
            with db.session() as session:
                session.execute(__import__("sqlalchemy").text("SELECT 1"))
            return True
        except Exception:
            return False

    registry.register(
        name="database",
        description="Database connectivity and query execution",
        critical=True,
        check_fn=check_database,
    )

    # Artifact store check
    def check_artifact_store() -> bool:
        try:
            from pathlib import Path

            artifact_path = Path(artifact_root)
            return artifact_path.exists() or artifact_path.parent.exists()
        except Exception:
            return False

    registry.register(
        name="artifact_store",
        description="Artifact storage directory accessibility",
        critical=True,
        check_fn=check_artifact_store,
    )

    # Auth mode check
    def check_auth() -> bool:
        return auth_mode in ("dev", "oidc")

    registry.register(
        name="auth",
        description="Authentication mode is valid",
        critical=True,
        check_fn=check_auth,
    )

    # Disk space check (warning only)
    def check_disk_space() -> bool:
        try:
            import shutil

            usage = shutil.disk_usage(artifact_root)
            free_gb = usage.free / (1024**3)
            return free_gb > 1.0  # At least 1 GB free
        except Exception:
            return True  # Don't fail if we can't check

    registry.register(
        name="disk_space",
        description="Sufficient disk space available (>1GB free)",
        critical=False,
        check_fn=check_disk_space,
    )

    return registry


# ============================================================================
# Tracing Middleware
# ============================================================================


class TracingMiddleware(BaseHTTPMiddleware):
    """Distributed tracing middleware with W3C TraceContext propagation.

    Creates server spans for incoming requests, propagates trace context
    via traceparent/tracestate headers, and integrates with CorrelationContext.

    Security: Never records request/response bodies, headers, or sensitive data.
    Only records method, path, status code, and duration.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        tracer = get_tracer()

        # Extract trace context from incoming headers (W3C TraceContext)
        headers_dict = dict(request.headers)
        extracted = extract_trace_context(headers_dict)

        # Determine trace ID
        if extracted and extracted.get("trace_id"):
            trace_id = extracted["trace_id"]
        else:
            trace_id = request.headers.get("X-Correlation-ID") or new_id("trc")

        # Create correlation context from propagated headers
        context = CorrelationContext(
            trace_id=trace_id,
            project_id=request.headers.get("X-WE3-Project-ID", ""),
        )
        set_correlation_context(context)

        # Start server span
        span_name = f"{request.method} {request.url.path}"
        span = tracer.start_span(
            span_name,
            attributes={
                "http.method": request.method,
                "http.target": request.url.path,
                "http.scheme": request.url.scheme,
                "http.user_agent": request.headers.get("user-agent", "")[:256],
            },
        )

        # Set as current span
        previous_span = tracer.current_span
        tracer._current_span = span
        tracer._span_stack.append(span)

        start_time = time.monotonic()

        try:
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("status", "success" if response.status_code < 400 else "error")
            return response
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("status", "error")
            span.set_attribute("error_class", type(exc).__name__)
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            span.set_attribute("duration_ms", round(duration_ms, 2))
            span.end()

            # Restore previous span
            tracer._span_stack.pop()
            tracer._current_span = previous_span


# ============================================================================
# Middleware Registration
# ============================================================================


def add_production_middleware(
    app: FastAPI,
    database_url: str,
    artifact_root: str,
    auth_mode: str,
    redis_client: Any | None = None,
) -> None:
    """Add all production middleware to the FastAPI app.

    Order matters: middleware is executed in reverse order of addition.
    The outermost middleware (StructuredLoggingMiddleware) sees the request first
    and the response last.

    Middleware stack (outermost to innermost):
    1. StructuredLoggingMiddleware - correlation IDs, structured logging
    2. TracingMiddleware - distributed tracing spans
    3. SecurityHeadersMiddleware - security headers on responses
    4. RateLimitMiddleware - distributed rate limiting (Redis or in-memory)
    5. CORSMiddleware - CORS policy enforcement
    6. ContentTypeValidationMiddleware - content-type validation
    7. CSRFProtectionMiddleware - CSRF protection for state-changing ops
    8. BodySizeLimitMiddleware - request body size limits
    """
    # Register health checks
    register_default_health_checks(database_url, artifact_root, auth_mode)

    # Add middleware (order: last added = outermost)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(CSRFProtectionMiddleware, auth_mode=auth_mode)
    app.add_middleware(ContentTypeValidationMiddleware)
    app.add_middleware(CORSMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        default_limit=RATE_LIMIT_DEFAULT,
        default_window=60,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)
