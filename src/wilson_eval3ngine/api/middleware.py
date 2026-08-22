"""Shared production middleware and the canonical API security composition facade.

This module owns only controls that do not have a stronger specialized
implementation elsewhere: structured request logging, response security headers,
content-type validation, health checks, and tracing.  Distributed rate limiting,
CORS enforcement, CSRF binding, and streaming body limits live in their dedicated
security modules and are composed through :func:`add_production_middleware`.

There is exactly one production implementation for each security boundary.
Compatibility attribute lookups at the bottom of this module resolve old import
names to those canonical implementations; they do not contain alternate logic.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..security.input_validation import ContentTypeValidator, ProjectIdValidator, ValidationError
from ..security.rate_limit import RateLimitConfig
from ..telemetry import CorrelationContext, get_correlation_context, set_correlation_context
from ..tracing import extract_trace_context, get_tracer
from ..util import new_id

logger = logging.getLogger("wilson.api.middleware")

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

# Browser security response policy. HSTS preload is a response directive only;
# browser preload-list enrollment remains a separate domain-owner operation.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # Disable obsolete browser XSS auditors rather than enabling historically
    # inconsistent filters. CSP is the supported script-execution boundary.
    "X-XSS-Protection": "0",
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
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "X-Permitted-Cross-Domain-Policies": "none",
}

RATE_LIMIT_DEFAULT = int(os.getenv("WE3_RATE_LIMIT_DEFAULT", "1000"))
RATE_LIMIT_AUTH = int(os.getenv("WE3_RATE_LIMIT_AUTH", "10"))
RATE_LIMIT_BURST = int(os.getenv("WE3_RATE_LIMIT_BURST", "20"))
MAX_BODY_SIZE = int(os.getenv("WE3_MAX_BODY_SIZE", str(10 * 1024 * 1024)))

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-CSRF-Token",
    "X-Correlation-ID",
    "X-WE3-Project-ID",
    "Idempotency-Key",
    "If-Match",
]
# Current production authentication uses an explicit Authorization bearer header,
# not ambient browser cookies. Do not advertise credentialed CORS by default.
CORS_ALLOW_CREDENTIALS = False
CORS_MAX_AGE = 3600

RATE_LIMIT_RULES: dict[str, RateLimitConfig] = {
    "/v1/experiments:validate": RateLimitConfig(RATE_LIMIT_DEFAULT),
    "/v1/experiments:run": RateLimitConfig(RATE_LIMIT_DEFAULT, burst=5),
    "/v1/auth/revoke": RateLimitConfig(RATE_LIMIT_AUTH, burst=0),
    "/health": RateLimitConfig(60),
    "/ready": RateLimitConfig(60, burst=0),
    "/metrics": RateLimitConfig(60),
}


def _safe_correlation_id(request: Request) -> str:
    supplied = request.headers.get("X-Correlation-ID", "")
    if supplied and _CORRELATION_ID.fullmatch(supplied):
        return supplied
    return new_id("trc")


def _safe_project_id(request: Request) -> str:
    supplied = request.headers.get("X-WE3-Project-ID", "")
    if not supplied:
        return ""
    try:
        return ProjectIdValidator.validate(supplied)
    except ValidationError:
        return ""


def _apply_security_headers(response: Response) -> None:
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers[header_name] = header_value


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Emit bounded structured request evidence without logging secret material.

    Security metadata is normalized at this outermost boundary so an invalid,
    attacker-controlled correlation identifier is never reflected into logs or a
    generated 500 response before inner validation has a chance to reject it.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = _safe_correlation_id(request)
        set_correlation_context(
            CorrelationContext(
                trace_id=correlation_id,
                project_id=_safe_project_id(request),
            )
        )
        start_time = time.monotonic()
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"
        anonymized_ip = self._anonymize_ip(client_host)

        error_detail: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # stable public error boundary
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
            # SecurityHeadersMiddleware is inside this boundary, so a response
            # created here must receive the same policy explicitly.
            _apply_security_headers(response)

        duration_ms = (time.monotonic() - start_time) * 1000
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
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @staticmethod
    def _anonymize_ip(value: str) -> str:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return "unknown"
        prefix = 24 if address.version == 4 else 48
        return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False).network_address)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply the API browser-security policy to every inner response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        _apply_security_headers(response)
        return response


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Reject parser/content-type confusion on endpoints with body contracts."""

    _JSON_ENDPOINTS = {
        "/v1/experiments:run",
        "/v1/experiments:validate",
        "/v1/operations",
    }
    _FORM_ENDPOINTS = {"/v1/auth/login"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_type = request.headers.get("Content-Type", "")
            validator = ContentTypeValidator()
            if request.url.path in self._JSON_ENDPOINTS:
                valid, _ = validator.validate_json(content_type)
                if not valid:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "schema_version": "we3.error.v1",
                            "code": "unsupported_media_type",
                            "retryable": False,
                            "safe_detail": "request content type must be application/json",
                            "trace_id": get_correlation_context().trace_id,
                        },
                    )
            elif request.url.path in self._FORM_ENDPOINTS:
                valid, _ = validator.validate_form(content_type)
                if not valid:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "schema_version": "we3.error.v1",
                            "code": "unsupported_media_type",
                            "retryable": False,
                            "safe_detail": "request content type is not supported",
                            "trace_id": get_correlation_context().trace_id,
                        },
                    )
        return await call_next(request)


@dataclass(frozen=True, slots=True)
class HealthCheck:
    name: str
    description: str
    critical: bool


class HealthCheckRegistry:
    """Registry of bounded readiness checks."""

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
        self._checks[name] = HealthCheck(name, description, critical)
        self._implementations[name] = check_fn

    def get_checks(self) -> list[HealthCheck]:
        return list(self._checks.values())

    def run_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {"checks": {}, "status": "ok", "critical_failures": []}
        for name, check in self._checks.items():
            try:
                passed = bool(self._implementations[name]())
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


_health_registry: HealthCheckRegistry | None = None


def get_health_registry() -> HealthCheckRegistry:
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    return _health_registry


def register_default_health_checks(
    database_url: str,
    artifact_root: str,
    auth_mode: str,
) -> HealthCheckRegistry:
    registry = get_health_registry()

    def check_database() -> bool:
        try:
            from sqlalchemy import text
            from ..persistence.database import Database

            db = Database(database_url)
            with db.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def check_artifact_store() -> bool:
        try:
            artifact_path = Path(artifact_root)
            return artifact_path.exists() or artifact_path.parent.exists()
        except Exception:
            return False

    def check_auth() -> bool:
        return auth_mode in {"dev", "oidc"}

    def check_disk_space() -> bool:
        try:
            import shutil

            return shutil.disk_usage(artifact_root).free > 1024**3
        except Exception:
            # Advisory check only; inability to inspect the filesystem does not
            # override the critical persistence/readiness checks above.
            return True

    registry.register("database", "Database connectivity and query execution", True, check_database)
    registry.register("artifact_store", "Artifact storage directory accessibility", True, check_artifact_store)
    registry.register("auth", "Authentication mode is valid", True, check_auth)
    registry.register("disk_space", "Sufficient disk space available (>1GB free)", False, check_disk_space)
    return registry


class TracingMiddleware(BaseHTTPMiddleware):
    """Create W3C-correlated server spans without recording request secrets."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        tracer = get_tracer()
        extracted = extract_trace_context(dict(request.headers))
        trace_id = (
            extracted["trace_id"]
            if extracted and extracted.get("trace_id")
            else _safe_correlation_id(request)
        )
        set_correlation_context(
            CorrelationContext(trace_id=trace_id, project_id=_safe_project_id(request))
        )

        span = tracer.start_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.target": request.url.path,
                "http.scheme": request.url.scheme,
                "http.user_agent": request.headers.get("user-agent", "")[:256],
            },
        )
        previous_span = tracer.current_span
        tracer._current_span = span
        tracer._span_stack.append(span)
        started = time.monotonic()
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
            span.set_attribute("duration_ms", round((time.monotonic() - started) * 1000, 2))
            span.end()
            tracer._span_stack.pop()
            tracer._current_span = previous_span


def add_production_middleware(
    app: FastAPI,
    database_url: str,
    artifact_root: str,
    auth_mode: str,
    redis_client: Any | None = None,
) -> None:
    """Compose the single supported API request-security boundary.

    Imports are intentionally local to avoid a module cycle: the specialized
    middleware module consumes the shared constants and classes above.
    """
    from ..security.redis_authority import RedisSecurityAuthority
    from .authorization_audit import AuthorizationAuditMiddleware
    from .security_middleware import add_hardened_production_middleware

    app.add_middleware(AuthorizationAuditMiddleware)
    security_redis = RedisSecurityAuthority(redis_client) if redis_client is not None else None
    add_hardened_production_middleware(
        app,
        database_url=database_url,
        artifact_root=artifact_root,
        auth_mode=auth_mode,
        redis_client=security_redis,
    )


def __getattr__(name: str) -> Any:
    """Resolve historical import names to canonical implementations only.

    This is a compatibility surface, not an alternate security path. New code
    should import the concrete classes from ``body_limit`` or
    ``security_middleware`` directly.
    """
    if name == "BodySizeLimitMiddleware":
        from .body_limit import StreamingBodyLimitMiddleware

        return StreamingBodyLimitMiddleware
    if name in {"CORSMiddleware", "RateLimitMiddleware", "CSRFProtectionMiddleware"}:
        from .security_middleware import (
            AuthoritativeRateLimitMiddleware,
            BoundCSRFProtectionMiddleware,
            StrictCORSMiddleware,
        )

        return {
            "CORSMiddleware": StrictCORSMiddleware,
            "RateLimitMiddleware": AuthoritativeRateLimitMiddleware,
            "CSRFProtectionMiddleware": BoundCSRFProtectionMiddleware,
        }[name]
    raise AttributeError(name)


__all__ = [
    "CORS_ALLOWED_HEADERS",
    "CORS_ALLOWED_METHODS",
    "CORS_ALLOW_CREDENTIALS",
    "CORS_MAX_AGE",
    "ContentTypeValidationMiddleware",
    "HealthCheck",
    "HealthCheckRegistry",
    "MAX_BODY_SIZE",
    "RATE_LIMIT_AUTH",
    "RATE_LIMIT_DEFAULT",
    "RATE_LIMIT_RULES",
    "SECURITY_HEADERS",
    "SecurityHeadersMiddleware",
    "StructuredLoggingMiddleware",
    "TracingMiddleware",
    "add_production_middleware",
    "get_health_registry",
    "register_default_health_checks",
]
