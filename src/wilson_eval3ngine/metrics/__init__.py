"""Metrics engine module for versioned performance and safety measurements.

Exports:
- MetricRegistry for definition management
- MetricComparison for A/B comparison logic
- DriftIndicator for change detection
- create_metric_snapshot for immutable evidence
"""

from .engine import (
    ComparisonStatus,
    DriftIndicator,
    MetricComparison,
    MetricDefinition,
    MetricDirection,
    MetricRegistry,
    check_comparison_eligibility,
    compute_metric_comparison,
    create_metric_snapshot,
    default_metric_registry,
    detect_metric_drift,
)

__all__ = [
    "MetricDirection",
    "MetricDefinition",
    "MetricRegistry",
    "default_metric_registry",
    "ComparisonStatus",
    "MetricComparison",
    "check_comparison_eligibility",
    "compute_metric_comparison",
    "create_metric_snapshot",
    "DriftIndicator",
    "detect_metric_drift",
]