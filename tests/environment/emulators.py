"""
Environment emulation framework for security control testing.

Provides EnvironmentConfig dataclass and environment-specific emulators
that simulate different deployment configurations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from unittest.mock import MagicMock


class EnvironmentType(StrEnum):
    """Types of deployment environments for testing."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    MINIMAL = "minimal"
    OTEL_ENABLED = "otel_enabled"
    OTEL_DISABLED = "otel_disabled"


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    """Configuration for a test environment.

    Encapsulates all environment-specific settings that affect
    how security controls behave.
    """
    env_type: EnvironmentType
    database_url: str
    artifact_root: str
    auth_mode: str
    environment: str
    oidc_issuer: str
    oidc_jwks_uri: str
    oidc_audience: str
    kms_master_key: str
    otel_enabled: bool
    otel_endpoint: str
    service_name: str
    service_version: str
    tracing_enabled: bool
    extra_env: dict[str, str] = field(default_factory=dict)

    def as_env_dict(self) -> dict[str, str]:
        """Return environment variables for this configuration."""
        env = {
            "WE3_DATABASE_URL": self.database_url,
            "WE3_ARTIFACT_ROOT": self.artifact_root,
            "WE3_AUTH_MODE": self.auth_mode,
            "WE3_ENVIRONMENT": self.environment,
            "WE3_OIDC_ISSUER": self.oidc_issuer,
            "WE3_OIDC_JWKS_URI": self.oidc_jwks_uri,
            "WE3_OIDC_AUDIENCE": self.oidc_audience,
            "WE3_KMS_MASTER_KEY": self.kms_master_key,
            "WE3_OTEL_ENABLED": "true" if self.otel_enabled else "false",
            "WE3_OTLP_ENDPOINT": self.otel_endpoint,
            "WE3_SERVICE_NAME": self.service_name,
            "WE3_SERVICE_VERSION": self.service_version,
            "WE3_TRACING_ENABLED": "true" if self.tracing_enabled else "false",
        }
        env.update(self.extra_env)
        return env

    def apply(self) -> dict[str, str]:
        """Apply environment variables and return previous values for restoration."""
        previous = {}
        for key, value in self.as_env_dict().items():
            previous[key] = os.environ.get(key)
            os.environ[key] = value
        return previous

    def restore(self, previous: dict[str, str]) -> None:
        """Restore environment variables to previous state."""
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ============================================================================
# Environment Definitions
# ============================================================================

class DevEnvironment(EnvironmentConfig):
    """Development environment: SQLite, local KMS, dev auth mode."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.DEVELOPMENT,
            database_url="sqlite://",
            artifact_root="/tmp/we3-dev-artifacts",
            auth_mode="dev",
            environment="development",
            oidc_issuer="",
            oidc_jwks_uri="",
            oidc_audience="wilson-eval3ngine-api",
            kms_master_key="dev_master_key_" + "x" * 24,  # 32+ bytes
            otel_enabled=False,
            otel_endpoint="http://localhost:4317",
            service_name="wilson-eval3ngine-dev",
            service_version="0.1.0-dev",
            tracing_enabled=True,
        )


class StagingEnvironment(EnvironmentConfig):
    """Staging environment: PostgreSQL (mocked), OIDC auth, external KMS."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.STAGING,
            database_url="postgresql://we3:we3pass@localhost:5432/we3_staging",
            artifact_root="/var/we3/staging/artifacts",
            auth_mode="oidc",
            environment="staging",
            oidc_issuer="https://auth.staging.example.com",
            oidc_jwks_uri="https://auth.staging.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine-staging",
            kms_master_key="staging_master_key_" + "x" * 22,  # 32+ bytes
            otel_enabled=True,
            otel_endpoint="http://otel-collector.staging:4317",
            service_name="wilson-eval3ngine-staging",
            service_version="0.1.0-staging",
            tracing_enabled=True,
        )


class ProductionEnvironment(EnvironmentConfig):
    """Production environment: Full production config validation."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.PRODUCTION,
            database_url="postgresql://we3:we3pass@db.prod:5432/we3_prod",
            artifact_root="/var/we3/prod/artifacts",
            auth_mode="oidc",
            environment="production",
            oidc_issuer="https://auth.prod.example.com",
            oidc_jwks_uri="https://auth.prod.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine-prod",
            kms_master_key="prod_master_key_" + "x" * 23,  # 32+ bytes
            otel_enabled=True,
            otel_endpoint="http://otel-collector.prod:4317",
            service_name="wilson-eval3ngine-prod",
            service_version="0.1.0",
            tracing_enabled=True,
        )


class MinimalEnvironment(EnvironmentConfig):
    """Minimal environment: No optional dependencies installed."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.MINIMAL,
            database_url="sqlite://",
            artifact_root="/tmp/we3-minimal-artifacts",
            auth_mode="dev",
            environment="development",
            oidc_issuer="",
            oidc_jwks_uri="",
            oidc_audience="wilson-eval3ngine-api",
            kms_master_key="minimal_master_key_" + "x" * 21,  # 32+ bytes
            otel_enabled=False,
            otel_endpoint="",
            service_name="wilson-eval3ngine-minimal",
            service_version="0.1.0",
            tracing_enabled=True,
            extra_env={
                "WE3_OTLP_INSECURE": "true",
            },
        )


class OTelEnabledEnvironment(EnvironmentConfig):
    """Environment with OpenTelemetry SDK available and initialized."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.OTEL_ENABLED,
            database_url="sqlite://",
            artifact_root="/tmp/we3-otel-artifacts",
            auth_mode="dev",
            environment="development",
            oidc_issuer="",
            oidc_jwks_uri="",
            oidc_audience="wilson-eval3ngine-api",
            kms_master_key="otel_master_key_" + "x" * 22,  # 32+ bytes
            otel_enabled=True,
            otel_endpoint="http://localhost:4317",
            service_name="wilson-eval3ngine-otel",
            service_version="0.1.0-otel",
            tracing_enabled=True,
        )


class OTelDisabledEnvironment(EnvironmentConfig):
    """Environment with OpenTelemetry SDK not available (graceful degradation)."""
    def __init__(self):
        super().__init__(
            env_type=EnvironmentType.OTEL_DISABLED,
            database_url="sqlite://",
            artifact_root="/tmp/we3-no-otel-artifacts",
            auth_mode="dev",
            environment="development",
            oidc_issuer="",
            oidc_jwks_uri="",
            oidc_audience="wilson-eval3ngine-api",
            kms_master_key="no_otel_master_key_" + "x" * 19,  # 32+ bytes
            otel_enabled=False,
            otel_endpoint="",
            service_name="wilson-eval3ngine-no-otel",
            service_version="0.1.0-no-otel",
            tracing_enabled=False,
        )


# ============================================================================
# Factory Functions
# ============================================================================

_ENVIRONMENT_REGISTRY: dict[EnvironmentType, type[EnvironmentConfig]] = {
    EnvironmentType.DEVELOPMENT: DevEnvironment,
    EnvironmentType.STAGING: StagingEnvironment,
    EnvironmentType.PRODUCTION: ProductionEnvironment,
    EnvironmentType.MINIMAL: MinimalEnvironment,
    EnvironmentType.OTEL_ENABLED: OTelEnabledEnvironment,
    EnvironmentType.OTEL_DISABLED: OTelDisabledEnvironment,
}


def create_environment(env_type: EnvironmentType) -> EnvironmentConfig:
    """Create an environment configuration by type."""
    cls = _ENVIRONMENT_REGISTRY.get(env_type)
    if cls is None:
        raise ValueError(f"Unknown environment type: {env_type}")
    return cls()


def get_all_environments() -> list[EnvironmentConfig]:
    """Get all environment configurations for parametrized testing."""
    return [create_environment(env_type) for env_type in EnvironmentType]


def get_security_relevant_environments() -> list[EnvironmentConfig]:
    """Get environments that are most relevant for security testing.

    These cover the key security-relevant scenarios:
    - Development (dev auth, SQLite)
    - Staging (OIDC, PostgreSQL, OTel)
    - Production (full validation)
    - Minimal (no optional deps)
    - OTel enabled/disabled (tracing behavior)
    """
    return [
        create_environment(EnvironmentType.DEVELOPMENT),
        create_environment(EnvironmentType.STAGING),
        create_environment(EnvironmentType.PRODUCTION),
        create_environment(EnvironmentType.MINIMAL),
        create_environment(EnvironmentType.OTEL_ENABLED),
        create_environment(EnvironmentType.OTEL_DISABLED),
    ]
