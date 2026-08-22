"""Wilson Eval3ngine API package security composition.

The historical middleware module remains import-compatible, but the supported
application composition replaces its provisional body-limit, CORS, rate-limit,
and registrar symbols with the hardened implementations before ``api.main``
constructs the FastAPI application. Sensitive log filtering, normalized Redis
security-state errors, and durable authorization auditing are bound here.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from ..security.log_redaction import install_sensitive_log_filter
from ..security.redis_authority import RedisSecurityAuthority
from . import middleware as _middleware
from .authorization_audit import AuthorizationAuditMiddleware
from .body_limit import StreamingBodyLimitMiddleware
from .security_middleware import (
    AuthoritativeRateLimitMiddleware,
    StrictCORSMiddleware,
    add_hardened_production_middleware,
)

install_sensitive_log_filter(logging.getLogger())
install_sensitive_log_filter(logging.getLogger("wilson"))

if "If-Match" not in _middleware.CORS_ALLOWED_HEADERS:
    _middleware.CORS_ALLOWED_HEADERS = [
        *_middleware.CORS_ALLOWED_HEADERS,
        "If-Match",
    ]


def _add_supported_security_middleware(
    app: FastAPI,
    database_url: str,
    artifact_root: str,
    auth_mode: str,
    redis_client: Any | None = None,
) -> None:
    # Add the authorization audit scope first so the hardened registrar's
    # request/security/logging middleware wraps it. An audit-generated 503 then
    # still receives ordinary security headers, correlation, and request logging.
    app.add_middleware(AuthorizationAuditMiddleware)

    security_redis = (
        RedisSecurityAuthority(redis_client) if redis_client is not None else None
    )
    add_hardened_production_middleware(
        app,
        database_url=database_url,
        artifact_root=artifact_root,
        auth_mode=auth_mode,
        redis_client=security_redis,
    )


_middleware.BodySizeLimitMiddleware = StreamingBodyLimitMiddleware
_middleware.CORSMiddleware = StrictCORSMiddleware
_middleware.RateLimitMiddleware = AuthoritativeRateLimitMiddleware
_middleware.add_production_middleware = _add_supported_security_middleware

__all__ = [
    "AuthorizationAuditMiddleware",
    "AuthoritativeRateLimitMiddleware",
    "StreamingBodyLimitMiddleware",
    "StrictCORSMiddleware",
    "add_hardened_production_middleware",
]
