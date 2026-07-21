"""Deployment and migration package for Wilson Eval3ngine.

Provides:
- Version-skew aware deployment controls
- Schema migration safety validation
- Blue-green/rolling deployment patterns
- Canary verification thresholds
- Evidence-preserving rollback
"""

from .deployment_controller import (
    ComponentType,
    CompatibilityMatrix,
    DeploymentController,
    DeploymentRecord,
    DeploymentState,
    DeploymentStrategy,
    MigrationPlan,
    VersionInfo,
    compute_deployment_digest,
)


__all__ = [
    "ComponentType",
    "CompatibilityMatrix",
    "DeploymentController",
    "DeploymentRecord",
    "DeploymentState",
    "DeploymentStrategy",
    "MigrationPlan",
    "VersionInfo",
    "compute_deployment_digest",
]