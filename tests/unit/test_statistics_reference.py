"""Unit tests for statistical reference implementation (TODO 32).

Tests cover:
- Wilson interval calculation matching production
- Cluster bootstrap with deterministic seeds
- Paired delta comparisons
- Edge cases (singleton clusters, degenerate samples)
"""

import math
import pytest

from wilson_eval3ngine.domain.contracts import Interval
from wilson_eval3ngine.statistics.intervals import wilson_interval as wilson_production
from wilson_eval3ngine.statistics.reference import (
    ClusterBootstrapConfig,
    ClusterBootstrapResult,
    PairedDeltaResult,
    cluster_bootstrap_reference,
    paired_delta_reference,
    validate_cluster_unit_assumption,
    wilson_interval_reference,
)


class TestWilsonInterval:
    """Test Wilson interval reference implementation."""

    def test_reference_matches_production(self):
        """Reference implementation should match production Wilson interval."""
        production = wilson_production(50, 100)
        reference = wilson_interval_reference(50, 100)

        assert production.lower == pytest.approx(reference.lower, abs=1e-5)
        assert production.upper == pytest.approx(reference.upper, abs=1e-5)
        assert production.confidence == reference.confidence

    def test_wilson_interval_basic(self):
        """Basic Wilson interval calculation."""
        interval = wilson_interval_reference(75, 100)

        assert isinstance(interval, Interval)
        assert interval.lower > 0.5
        assert interval.upper < 0.85
        assert interval.confidence == 0.95

    def test_wilson_interval_zero_successes(self):
        """Zero successes yields valid interval."""
        interval = wilson_interval_reference(0, 100)

        assert interval is not None
        assert interval.lower == 0.0
        assert interval.upper < 0.05

    def test_wilson_interval_all_successes(self):
        """All successes yields valid interval."""
        interval = wilson_interval_reference(100, 100)

        assert interval is not None
        assert interval.lower > 0.95
        assert interval.upper == pytest.approx(1.0, abs=1e-10)

    def test_wilson_interval_zero_total(self):
        """Zero total returns None."""
        assert wilson_interval_reference(0, 0) is None

    def test_wilson_interval_invalid_successes(self):
        """Invalid successes raises error."""
        with pytest.raises(ValueError):
            wilson_interval_reference(-1, 100)

        with pytest.raises(ValueError):
            wilson_interval_reference(150, 100)


class TestClusterBootstrap:
    """Test cluster bootstrap reference implementation."""

    def test_bootstrap_deterministic(self):
        """Bootstrap is deterministic with fixed seed."""
        data = {
            1: [1.0, 0.9, 1.0],
            2: [0.8, 0.9, 0.8],
            3: [1.0, 1.0, 0.9],
        }

        config = ClusterBootstrapConfig(seed=42, resample_count=100)
        r1 = cluster_bootstrap_reference(data, config)
        r2 = cluster_bootstrap_reference(data, config)

        assert r1.observed_value == r2.observed_value
        assert r1.bootstrap_mean == r2.bootstrap_mean

    def test_bootstrap_result_structure(self):
        """Bootstrap result has correct structure."""
        data = {1: [0.9, 0.8], 2: [0.7, 0.8]}
        result = cluster_bootstrap_reference(data)

        assert isinstance(result, ClusterBootstrapResult)
        assert result.statistic == "proportion"
        assert 0.0 <= result.observed_value <= 1.0
        assert result.percentile_lower <= result.percentile_upper

    def test_bootstrap_singleton_cluster(self):
        """Singleton clusters handled gracefully with min_clusters=1."""
        data = {1: [1.0]}
        config = ClusterBootstrapConfig(seed=42, resample_count=100, min_clusters=1)
        result = cluster_bootstrap_reference(data, config)

        assert isinstance(result, ClusterBootstrapResult)
        assert result.observed_value == 1.0

    def test_bootstrap_insufficient_clusters(self):
        """Insufficient clusters yield indeterminate result."""
        min_config = ClusterBootstrapConfig(seed=42, resample_count=100, min_clusters=5)
        data = {1: [1.0], 2: [0.0]}

        result = cluster_bootstrap_reference(data, min_config)

        assert result.observed_value == 0.0  # Indeterminate


class TestPairedDelta:
    """Test paired delta comparison reference implementation."""

    def test_paired_delta_no_difference(self):
        """No difference yields zero mean delta."""
        baseline = [0.9, 0.8, 0.95]
        candidate = [0.9, 0.8, 0.95]

        result = paired_delta_reference(baseline, candidate)

        assert result.difference_mean == 0.0
        assert (0.0, 0.0) == result.confidence_interval

    def test_paired_delta_improvement(self):
        """Positive difference indicates improvement."""
        baseline = [0.7, 0.7, 0.7]
        candidate = [0.9, 0.9, 0.9]

        result = paired_delta_reference(baseline, candidate)

        assert result.difference_mean == pytest.approx(0.2)

    def test_paired_delta_lengths_must_match(self):
        """Mismatched lengths raise error."""
        with pytest.raises(ValueError):
            paired_delta_reference([1, 2], [1, 2, 3])


class TestClusterValidation:
    """Test cluster unit validation."""

    def test_validate_cluster_hierarchy(self):
        """Cluster validation returns analysis structure."""
        hierarchy = {
            "families": {
                "family_a": {"cases": [1, 2, 3]},
                "family_b": {"cases": [4, 5]},
            }
        }

        result = validate_cluster_unit_assumption(hierarchy)

        assert "families_analyzed" in result
        assert result["families_analyzed"] == 2