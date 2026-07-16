"""Statistical analysis module for confidence intervals and bootstrap resampling.

Exports:
- Wilson score intervals for binomial proportion confidence
- Cluster bootstrap for hierarchical data
- Paired delta comparisons for A/B testing
"""

from .intervals import wilson_interval
from .reference import (
    ClusterBootstrapConfig,
    ClusterBootstrapResult,
    PairedDeltaResult,
    cluster_bootstrap_reference,
    paired_delta_reference,
    validate_cluster_unit_assumption,
    wilson_interval_reference,
)

__all__ = [
    "wilson_interval",
    "ClusterBootstrapConfig",
    "ClusterBootstrapResult",
    "PairedDeltaResult",
    "cluster_bootstrap_reference",
    "paired_delta_reference",
    "validate_cluster_unit_assumption",
    "wilson_interval_reference",
]