"""
Unit tests for production middleware: structured logging, security headers,
rate limiting, body size limits, and health checks.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from wilson_eval3ngine.api.middleware import (
    BodySizeLimitMiddleware,
    HealthCheck,
    HealthCheckRegistry,
    MAX_BODY_SIZE,
    RateLimitConfig,
    RateLimitMiddleware,
    SECURITY_HEADERS,
    SecurityHeadersMiddleware,
    StructuredLoggingMiddleware,
    add_production_middleware,
    get_health_registry,
    register_default_health_checks,
)


# ============================================================================
# Structured Logging Middleware Tests
# ============================================================================


def test_structured_logging_adds_correlation_id():
    """StructuredLoggingMiddleware should add X-Correlation-ID header."""
    app = FastAPI()
    app.add_middleware(StructuredLoggingMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0


def test_structured_logging_propagates_correlation_id():
    """StructuredLoggingMiddleware should propagate existing X-Correlation-ID."""
    app = FastAPI()
    app.add_middleware(StructuredLoggingMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    trace_id = "test-trace-12345"
    response = client.get("/test", headers={"X-Correlation-ID": trace_id})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == trace_id


def test_structured_logging_handles_exceptions():
    """StructuredLoggingMiddleware should catch exceptions and return 500."""
    app = FastAPI()
    app.add_middleware(StructuredLoggingMiddleware)

    @app.get("/error")
    def error_endpoint():
        raise RuntimeError("test error")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/error")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "X-Correlation-ID" in response.headers


def test_structured_logging_anonymizes_ip():
    """StructuredLoggingMiddleware should anonymize client IP addresses."""
    middleware = StructuredLoggingMiddleware.__new__(StructuredLoggingMiddleware)
    assert middleware._anonymize_ip("192.168.1.100") == "192.168.1.0"
    assert middleware._anonymize_ip("10.0.0.1") == "10.0.0.0"
    assert middleware._anonymize_ip("unknown") == "unknown"


# ============================================================================
# Security Headers Middleware Tests
# ============================================================================


def test_security_headers_present():
    """SecurityHeadersMiddleware should add all security headers."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    for header_name, header_value in SECURITY_HEADERS.items():
        assert response.headers[header_name] == header_value, (
            f"Missing or incorrect header: {header_name}"
        )


def test_security_headers_csp():
    """Content-Security-Policy header should be restrictive."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'self'" in csp


def test_security_headers_hsts():
    """Strict-Transport-Security header should be present with long max-age."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    hsts = response.headers["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


# ============================================================================
# Rate Limiting Middleware Tests
# ============================================================================


def test_rate_limit_allows_requests_under_limit():
    """RateLimitMiddleware should allow requests under the limit."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(10):
        response = client.get("/test")
        assert response.status_code == 200


def test_rate_limit_blocks_excess_requests():
    """RateLimitMiddleware should block requests exceeding the limit."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)

    # The default limit is 1000 per minute, so we need to exceed it
    # Instead, test with a custom low limit
    app2 = FastAPI()
    app2.add_middleware(RateLimitMiddleware)

    @app2.get("/test")
    def test_endpoint2():
        return {"ok": True}

    # Patch the rate limit rules to have a very low limit
    with patch("wilson_eval3ngine.api.middleware.RATE_LIMIT_RULES", {
        "/test": RateLimitConfig(requests_per_minute=3, burst=1),
    }):
        client2 = TestClient(app2)
        for _ in range(3):
            response = client2.get("/test")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client2.get("/test")
        assert response.status_code == 429
        assert response.json()["code"] == "rate_limit_exceeded"
        assert "Retry-After" in response.headers


def test_rate_limit_includes_headers():
    """RateLimitMiddleware should include rate limit headers in responses."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


# ============================================================================
# Body Size Limit Middleware Tests
# ============================================================================


def test_body_size_limit_rejects_large_bodies():
    """BodySizeLimitMiddleware should reject bodies exceeding the limit."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware)

    @app.post("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)

    # Create a body larger than MAX_BODY_SIZE
    large_body = "x" * (MAX_BODY_SIZE + 1)
    response = client.post(
        "/test",
        content=large_body,
        headers={"Content-Length": str(len(large_body))},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_body_size_limit_allows_small_bodies():
    """BodySizeLimitMiddleware should allow bodies under the limit."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware)

    @app.post("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.post("/test", json={"data": "small body"})

    assert response.status_code == 200


# ============================================================================
# Health Check Tests
# ============================================================================


def test_health_check_registry_register_and_run():
    """HealthCheckRegistry should register and run health checks."""
    registry = HealthCheckRegistry()

    registry.register(
        name="test_check",
        description="A test check",
        critical=True,
        check_fn=lambda: True,
    )

    results = registry.run_all()
    assert results["status"] == "ok"
    assert results["checks"]["test_check"]["status"] == "pass"
    assert results["critical_failures"] == []


def test_health_check_registry_detects_failures():
    """HealthCheckRegistry should detect critical check failures."""
    registry = HealthCheckRegistry()

    registry.register(
        name="failing_check",
        description="A failing check",
        critical=True,
        check_fn=lambda: False,
    )

    results = registry.run_all()
    assert results["status"] == "degraded"
    assert results["checks"]["failing_check"]["status"] == "fail"
    assert "failing_check" in results["critical_failures"]


def test_health_check_registry_handles_exceptions():
    """HealthCheckRegistry should handle exceptions in check functions."""
    registry = HealthCheckRegistry()

    def failing_check():
        raise ValueError("check error")

    registry.register(
        name="error_check",
        description="A check that raises",
        critical=True,
        check_fn=failing_check,
    )

    results = registry.run_all()
    assert results["status"] == "degraded"
    assert results["checks"]["error_check"]["status"] == "error"
    assert "error_check" in results["critical_failures"]


def test_health_check_non_critical_failure():
    """Non-critical check failures should not mark status as degraded."""
    registry = HealthCheckRegistry()

    registry.register(
        name="warning_check",
        description="A non-critical check",
        critical=False,
        check_fn=lambda: False,
    )

    results = registry.run_all()
    assert results["status"] == "ok"  # Non-critical failures don't degrade
    assert results["checks"]["warning_check"]["status"] == "fail"
    assert results["critical_failures"] == []


def test_register_default_health_checks():
    """register_default_health_checks should register expected checks."""
    registry = register_default_health_checks(
        database_url="sqlite://",
        artifact_root="/tmp",
        auth_mode="dev",
    )

    checks = registry.get_checks()
    check_names = {c.name for c in checks}
    assert "database" in check_names
    assert "artifact_store" in check_names
    assert "auth" in check_names
    assert "disk_space" in check_names


def test_get_health_registry_singleton():
    """get_health_registry should return the same instance."""
    reg1 = get_health_registry()
    reg2 = get_health_registry()
    assert reg1 is reg2


# ============================================================================
# Full Middleware Integration Tests
# ============================================================================


def test_add_production_middleware(db, tmp_path):
    """add_production_middleware should add all middleware to the app."""
    app = FastAPI()

    add_production_middleware(
        app,
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
    )

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    # Security headers should be present
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    # Correlation ID should be present
    assert "X-Correlation-ID" in response.headers
    # Rate limit headers should be present
    assert "X-RateLimit-Limit" in response.headers


def test_health_endpoint_returns_ok(db):
    """The /health endpoint should return 200 with status ok."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root="/tmp",
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["schema_version"] == "we3.health.v1"


def test_readiness_endpoint_returns_ok(db, tmp_path):
    """The /ready endpoint should return 200 when all checks pass."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert "checks" in response.json()
    assert "uptime_seconds" in response.json()


def test_readiness_endpoint_returns_503_when_degraded(db, tmp_path):
    """The /ready endpoint should return 503 when critical checks fail."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings
    from wilson_eval3ngine.api.middleware import HealthCheckRegistry

    # Create a registry with a failing critical check
    registry = HealthCheckRegistry()
    registry.register(
        name="failing_db",
        description="Database check",
        critical=True,
        check_fn=lambda: False,
    )

    # Patch the global registry
    with patch("wilson_eval3ngine.api.middleware._health_registry", registry):
        settings = Settings(
            database_url="sqlite://",
            artifact_root=str(tmp_path),
            auth_mode="dev",
            environment="test",
        )
        app = create_app(settings, database=db)

        client = TestClient(app)
        response = client.get("/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
        assert "failing_db" in response.json()["critical_failures"]


def test_metrics_endpoint_returns_prometheus_format(db, tmp_path):
    """The /metrics endpoint should return Prometheus text format."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "we3_info" in body
    assert "we3_uptime_seconds" in body
    assert "we3_health_check" in body


def test_metrics_endpoint_includes_health_checks(db, tmp_path):
    """The /metrics endpoint should include health check metrics."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    response = client.get("/metrics")

    body = response.text
    assert 'we3_health_check{name="database"' in body
    assert 'we3_health_check{name="artifact_store"' in body
    assert 'we3_health_check{name="auth"' in body


def test_security_headers_on_all_responses(db, tmp_path):
    """Security headers should be present on all responses including errors."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    response = client.get("/nonexistent")

    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_correlation_id_propagated_through_middleware(db, tmp_path):
    """Correlation ID should be propagated through all middleware layers."""
    from wilson_eval3ngine.api.main import create_app
    from wilson_eval3ngine.config import Settings

    settings = Settings(
        database_url="sqlite://",
        artifact_root=str(tmp_path),
        auth_mode="dev",
        environment="test",
    )
    app = create_app(settings, database=db)

    client = TestClient(app)
    trace_id = "test-correlation-id-999"
    response = client.get(
        "/health",
        headers={"X-Correlation-ID": trace_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == trace_id
