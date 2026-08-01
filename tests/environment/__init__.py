"""
Environment emulation framework for security control testing.

This package provides fixtures and utilities for emulating different
deployment environments (development, staging, production) to verify
that security controls behave correctly across all environments.

Environments emulated:
- Development: SQLite, local KMS, dev auth mode, local artifact storage
- Staging: PostgreSQL (mocked), OIDC auth, external KMS, external storage
- Production: Full production config validation, all security controls active
- Minimal: No optional dependencies (jose, opentelemetry not installed)
- OTel-Enabled: OpenTelemetry SDK available and initialized
- OTel-Disabled: OpenTelemetry SDK not available (graceful degradation)
"""

from .emulators import (
    EnvironmentType,
    EnvironmentConfig,
    DevEnvironment,
    StagingEnvironment,
    ProductionEnvironment,
    MinimalEnvironment,
    OTelEnabledEnvironment,
    OTelDisabledEnvironment,
    create_environment,
    get_all_environments,
)

__all__ = [
    "EnvironmentType",
    "EnvironmentConfig",
    "DevEnvironment",
    "StagingEnvironment",
    "ProductionEnvironment",
    "MinimalEnvironment",
    "OTelEnabledEnvironment",
    "OTelDisabledEnvironment",
    "create_environment",
    "get_all_environments",
]
