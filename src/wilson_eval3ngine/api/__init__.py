"""Wilson Eval3ngine API package security composition.

The historical middleware module remains import-compatible, but the supported
application composition replaces its provisional body-limit, CORS, rate-limit,
and registrar symbols with the hardened implementations before ``api.main``
constructs the FastAPI application. Sensitive log filtering is installed at the
package boundary as well, so the direct and external-secret entrypoints receive
the same credential-redaction behavior.
"""

from __future__ import annotations

import logging

from ..security.log_redaction import install_sensitive_log_filter
from . import middleware as _middleware
from .body_limit import StreamingBodyLimitMiddleware
from .security_middleware import (
    AuthoritativeRateLimitMiddleware,
    StrictCORSMiddleware,
    add_hardened_production_middleware,
)

install_sensitive_log_filter(logging.getLogger())
install_sensitive_log_filter(logging.getLogger("wilson"))

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
