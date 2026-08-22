from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
# Importing the API package performs the supported composition overrides before
# api.main constructs the application.
import wilson_eval3ngine.api  # noqa: F401
from starlette.requests import Request

from wilson_eval3ngine.api import middleware
from wilson_eval3ngine.api.auth import extract_single_bearer_token
from wilson_eval3ngine.api.body_limit import StreamingBodyLimitMiddleware
from wilson_eval3ngine.api.security_middleware import (
    AuthoritativeRateLimitMiddleware,
    RequestMetadataValidationMiddleware,
    StrictCORSMiddleware,
)


def _request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "server": ("we3.invalid", 443),
            "path": "/v1/experiments/example",
            "raw_path": b"/v1/experiments/example",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
        }
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


def test_single_bearer_parser_accepts_exactly_one_bounded_ascii_header() -> None:
    request = _request_with_headers([(b"authorization", b"Bearer signed.jwt.token")])
    assert extract_single_bearer_token(request) == "signed.jwt.token"


def test_single_bearer_parser_rejects_duplicate_authorization_headers() -> None:
    request = _request_with_headers(
        [
            (b"authorization", b"Bearer first.jwt.token"),
            (b"authorization", b"Bearer second.jwt.token"),
        ]
    )
    assert extract_single_bearer_token(request) is None


def test_single_bearer_parser_rejects_malformed_or_non_ascii_values() -> None:
    assert extract_single_bearer_token(
        _request_with_headers([(b"authorization", b"Basic abc")])
    ) is None
    assert extract_single_bearer_token(
        _request_with_headers([(b"authorization", b"Bearer \xff")])
    ) is None


def _metadata_guard_app(*, assurance: bool) -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(is_assurance_environment=assurance)
    app.add_middleware(RequestMetadataValidationMiddleware)

    @app.post("/v1/experiments:run")
    def synchronous_run() -> dict[str, bool]:
        return {"executed": True}

    return app


def test_synchronous_filesystem_run_lane_is_disabled_in_assurance() -> None:
    client = TestClient(_metadata_guard_app(assurance=True))
    response = client.post("/v1/experiments:run")

    assert response.status_code == 403
    assert response.json()["code"] == "synchronous_execution_disabled"


def test_synchronous_run_lane_remains_available_for_local_development() -> None:
    client = TestClient(_metadata_guard_app(assurance=False))
    response = client.post("/v1/experiments:run")

    assert response.status_code == 200
    assert response.json() == {"executed": True}
