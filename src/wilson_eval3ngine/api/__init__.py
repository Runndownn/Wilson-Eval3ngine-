"""Wilson Eval3ngine API package.

The package exposes the canonical request-security components without mutating
submodules at import time. Production composition is owned by
``api.middleware.add_production_middleware`` and the specialized hardened
implementations it delegates to.
"""

from __future__ import annotations

import logging

from ..security.log_redaction import install_sensitive_log_filter
from .authorization_audit import AuthorizationAuditMiddleware
from .body_limit import StreamingBodyLimitMiddleware
from .middleware import add_production_middleware
from .security_middleware import (
    AuthoritativeRateLimitMiddleware,
    BoundCSRFProtectionMiddleware,
    RequestMetadataValidationMiddleware,
    StrictCORSMiddleware,
    add_hardened_production_middleware,
)

# Logging redaction is process-wide defense in depth and is intentionally
# installed at package composition. It does not change application semantics.
install_sensitive_log_filter(logging.getLogger())
install_sensitive_log_filter(logging.getLogger("wilson"))

__all__ = [
    "AuthorizationAuditMiddleware",
    "AuthoritativeRateLimitMiddleware",
    "BoundCSRFProtectionMiddleware",
    "RequestMetadataValidationMiddleware",
    "StreamingBodyLimitMiddleware",
    "StrictCORSMiddleware",
    "add_hardened_production_middleware",
    "add_production_middleware",
]
