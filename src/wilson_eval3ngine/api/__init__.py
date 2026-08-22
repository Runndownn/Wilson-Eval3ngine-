"""Wilson Eval3ngine API package security composition.

The historical middleware module remains import-compatible, but the supported
application composition replaces its provisional body-limit, CORS, rate-limit,
and registrar symbols with the hardened implementations before ``api.main``
constructs the FastAPI application. Keeping the replacement at the package
boundary preserves existing imports while there is only one supported runtime
security stack.
"""

from __future__ import annotations

from . import middleware as _middleware
from .body_limit import StreamingBodyLimitMiddleware
from .security_middleware import (
    AuthoritativeRateLimitMiddleware,
    StrictCORSMiddleware,
    add_hardened_production_middleware,
)

_middleware.BodySizeLimitMiddleware = StreamingBodyLimitMiddleware
_middleware.CORSMiddleware = StrictCORSMiddleware
_middleware.RateLimitMiddleware = AuthoritativeRateLimitMiddleware
_middleware.add_production_middleware = add_hardened_production_middleware

__all__ = [
    "AuthoritativeRateLimitMiddleware",
    "StreamingBodyLimitMiddleware",
    "StrictCORSMiddleware",
    "add_hardened_production_middleware",
]
