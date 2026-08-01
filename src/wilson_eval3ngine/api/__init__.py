"""Wilson Eval3ngine API package hardening composition.

The production middleware registrar resolves ``BodySizeLimitMiddleware`` when
it constructs the application stack.  Replace the legacy header-only class at
package initialization so every supported API entry point receives the actual
ASGI stream bound without duplicating route or application composition.
"""

from __future__ import annotations

from . import middleware as _middleware
from .body_limit import StreamingBodyLimitMiddleware

_middleware.BodySizeLimitMiddleware = StreamingBodyLimitMiddleware

__all__ = ["StreamingBodyLimitMiddleware"]
