"""
Pytest fixtures for environment emulation in security control tests.

Provides fixtures that:
- Apply environment variables for different deployment configurations
- Mock database backends (PostgreSQL vs SQLite)
- Mock optional dependencies (jose, opentelemetry)
- Restore environment state after tests
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from .emulators import (
    EnvironmentConfig,
    EnvironmentType,
    create_environment,
    get_security_relevant_environments,
)


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture
def env_config() -> EnvironmentConfig:
    """Default environment config (development)."""
    return create_environment(EnvironmentType.DEVELOPMENT)


@pytest.fixture
def env_dev() -> EnvironmentConfig:
    """Development environment configuration."""
    return create_environment(EnvironmentType.DEVELOPMENT)


@pytest.fixture
def env_staging() -> EnvironmentConfig:
    """Staging environment configuration."""
    return create_environment(EnvironmentType.STAGING)


@pytest.fixture
def env_production() -> EnvironmentConfig:
    """Production environment configuration."""
    return create_environment(EnvironmentType.PRODUCTION)


@pytest.fixture
def env_minimal() -> EnvironmentConfig:
    """Minimal environment configuration (no optional deps)."""
    return create_environment(EnvironmentType.MINIMAL)


@pytest.fixture
def env_otel_enabled() -> EnvironmentConfig:
    """Environment with OpenTelemetry SDK enabled."""
    return create_environment(EnvironmentType.OTEL_ENABLED)


@pytest.fixture
def env_otel_disabled() -> EnvironmentConfig:
    """Environment with OpenTelemetry SDK disabled."""
    return create_environment(EnvironmentType.OTEL_DISABLED)


@pytest.fixture
def all_environments() -> list[EnvironmentConfig]:
    """All security-relevant environment configurations."""
    return get_security_relevant_environments()


# ============================================================================
# Environment Application Fixtures
# ============================================================================

@pytest.fixture
def applied_env(env_config: EnvironmentConfig):
    """Apply environment variables and restore after test."""
    previous = env_config.apply()
    yield env_config
    env_config.restore(previous)


@pytest.fixture
def applied_env_dev(env_dev: EnvironmentConfig):
    """Apply development environment variables."""
    previous = env_dev.apply()
    yield env_dev
    env_dev.restore(previous)


@pytest.fixture
def applied_env_staging(env_staging: EnvironmentConfig):
    """Apply staging environment variables."""
    previous = env_staging.apply()
    yield env_staging
    env_staging.restore(previous)


@pytest.fixture
def applied_env_production(env_production: EnvironmentConfig):
    """Apply production environment variables."""
    previous = env_production.apply()
    yield env_production
    env_production.restore(previous)


@pytest.fixture
def applied_env_otel_enabled(env_otel_enabled: EnvironmentConfig):
    """Apply OTel-enabled environment variables."""
    previous = env_otel_enabled.apply()
    yield env_otel_enabled
    env_otel_enabled.restore(previous)


@pytest.fixture
def applied_env_otel_disabled(env_otel_disabled: EnvironmentConfig):
    """Apply OTel-disabled environment variables."""
    previous = env_otel_disabled.apply()
    yield env_otel_disabled
    env_otel_disabled.restore(previous)


# ============================================================================
# Database Backend Mocks
# ============================================================================

@pytest.fixture
def mock_postgresql_session():
    """Mock SQLAlchemy session that reports PostgreSQL backend."""
    session = MagicMock()
    session.bind = MagicMock()
    session.bind.url = MagicMock()
    session.bind.url.__str__ = MagicMock(
        return_value="postgresql://we3:we3pass@localhost:5432/we3"
    )
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.get = MagicMock(return_value=None)
    session.query = MagicMock(return_value=MagicMock())
    session.close = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=None)
    return session


@pytest.fixture
def mock_sqlite_session():
    """Mock SQLAlchemy session that reports SQLite backend."""
    session = MagicMock()
    session.bind = MagicMock()
    session.bind.url = MagicMock()
    session.bind.url.__str__ = MagicMock(return_value="sqlite:///test.db")
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.get = MagicMock(return_value=None)
    session.query = MagicMock(return_value=MagicMock())
    session.close = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=None)
    return session


# ============================================================================
# Optional Dependency Mocks
# ============================================================================

@pytest.fixture
def mock_jose_available():
    """Mock python-jose as available."""
    mock_jose = MagicMock()
    mock_jwt = MagicMock()
    mock_jwt.get_unverified_header = MagicMock(return_value={"kid": "test-key"})
    mock_jwt.get_unverified_claims = MagicMock(return_value={"sub": "user123"})
    mock_jwt.decode = MagicMock(return_value={"sub": "user123", "we3_project_id": "proj1", "we3_role": "viewer"})
    mock_jose.jwt = mock_jwt
    mock_jose.JWTError = Exception

    mock_jwk = MagicMock()
    mock_jwk.construct = MagicMock(return_value=MagicMock())
    mock_jwk.construct.return_value.public_key = MagicMock(return_value="mock_pem_key")
    mock_jose.jwk = mock_jwk

    with patch.dict("sys.modules", {"jose": mock_jose, "jose.jwt": mock_jwt, "jose.jwk": mock_jwk}):
        yield mock_jose


@pytest.fixture
def mock_jose_unavailable():
    """Mock python-jose as unavailable."""
    with patch.dict("sys.modules", {"jose": None}):
        yield None


@pytest.fixture
def mock_opentelemetry_available():
    """Mock OpenTelemetry SDK as available and initialized."""
    from wilson_eval3ngine.observability import instrumentation as instr

    # Save original state
    original_otel_available = instr._OTEL_AVAILABLE
    original_otel_initialized = instr._OTEL_INITIALIZED

    # Set to available and initialized
    instr._OTEL_AVAILABLE = True
    instr._OTEL_INITIALIZED = True

    # Mock the tracer
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.name = "test.span"
    mock_span.trace_id = "test_trace_id"
    mock_span.span_id = "test_span_id"
    mock_span.parent_span_id = ""
    mock_span.is_recording = True
    mock_span.attributes = {}
    mock_span.events = []
    mock_span.set_attribute = MagicMock()
    mock_span.set_attributes = MagicMock()
    mock_span.add_event = MagicMock()
    mock_span.record_exception = MagicMock()
    mock_span.end = MagicMock()
    mock_tracer.start_span = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_span = MagicMock(return_value=MagicMock())

    with patch(
        "wilson_eval3ngine.observability.instrumentation.get_opentelemetry_tracer",
        return_value=mock_tracer,
    ):
        yield mock_tracer

    # Restore original state
    instr._OTEL_AVAILABLE = original_otel_available
    instr._OTEL_INITIALIZED = original_otel_initialized


@pytest.fixture
def mock_opentelemetry_unavailable():
    """Mock OpenTelemetry SDK as unavailable."""
    from wilson_eval3ngine.observability import instrumentation as instr

    original_otel_available = instr._OTEL_AVAILABLE
    original_otel_initialized = instr._OTEL_INITIALIZED

    instr._OTEL_AVAILABLE = False
    instr._OTEL_INITIALIZED = False

    yield None

    instr._OTEL_AVAILABLE = original_otel_available
    instr._OTEL_INITIALIZED = original_otel_initialized


# ============================================================================
# Combined Environment + Dependency Fixtures
# ============================================================================

@pytest.fixture
def env_dev_with_deps(applied_env_dev, mock_jose_available, mock_opentelemetry_unavailable):
    """Development environment with jose available and OTel unavailable."""
    return applied_env_dev


@pytest.fixture
def env_staging_with_deps(applied_env_staging, mock_jose_available, mock_opentelemetry_available):
    """Staging environment with jose and OTel available."""
    return applied_env_staging


@pytest.fixture
def env_production_with_deps(applied_env_production, mock_jose_available, mock_opentelemetry_available):
    """Production environment with jose and OTel available."""
    return applied_env_production


@pytest.fixture
def env_minimal_with_deps(applied_env_dev, mock_jose_unavailable, mock_opentelemetry_unavailable):
    """Minimal environment with no optional dependencies."""
    return applied_env_dev
