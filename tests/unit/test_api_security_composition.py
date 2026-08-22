from __future__ import annotations

# Importing the API package performs the supported composition overrides before
# api.main constructs the application.
import wilson_eval3ngine.api  # noqa: F401
from wilson_eval3ngine.api import middleware
from wilson_eval3ngine.api.body_limit import StreamingBodyLimitMiddleware
from wilson_eval3ngine.api.security_middleware import (
    AuthoritativeRateLimitMiddleware,
    StrictCORSMiddleware,
)


def test_supported_package_replaces_provisional_security_middlewares() -> None:
    assert middleware.BodySizeLimitMiddleware is StreamingBodyLimitMiddleware
    assert middleware.RateLimitMiddleware is AuthoritativeRateLimitMiddleware
    assert middleware.CORSMiddleware is StrictCORSMiddleware


def test_self_revocation_is_bodyless_and_has_dedicated_rate_limit() -> None:
    assert (
        "/v1/auth/revoke"
        not in middleware.ContentTypeValidationMiddleware._JSON_ENDPOINTS
    )
    rule = middleware.RATE_LIMIT_RULES["/v1/auth/revoke"]
    assert rule.requests_per_minute == middleware.RATE_LIMIT_AUTH
    assert rule.burst == 0


def test_readiness_is_bounded_even_though_public_caddy_denies_it() -> None:
    rule = middleware.RATE_LIMIT_RULES["/ready"]
    assert rule.requests_per_minute == 60
    assert rule.burst == 0


def test_conditional_request_header_is_in_browser_preflight_contract() -> None:
    assert "If-Match" in middleware.CORS_ALLOWED_HEADERS
