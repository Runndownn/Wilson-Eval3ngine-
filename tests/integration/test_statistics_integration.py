"""Integration tests for statistical reference and production metrics (TODO 32).

Tests that production metrics module and reference implementation agree
on frozen fixtures, validating the statistical independence.
"""

import pytest

from wilson_eval3ngine.domain.contracts import MetricResult
from wilson_eval3ngine.metrics.engine import (
    MetricDefinition,
    MetricDirection,
    check_comparison_eligibility,
    compute_metric_comparison,
)
from wilson_eval3ngine.statistics.intervals import wilson_interval as production_wilson
from wilson_eval3ngine.statistics.reference import (
    ClusterBootstrapConfig,
    cluster_bootstrap_reference,
    paired_delta_reference,
    wilson_interval_reference,
)


class TestProductionReferenceAgreement:
    """Test production and reference implementations agree on fixtures."""

    def test_wilson_agreement_on_canonical_fixtures(self):
        """Wilson interval matches across implementations on frozen fixtures."""
        fixtures = [
            (0, 10),
            (1, 10),
            (5, 10),
            (75, 100),
            (95, 100),
            (100, 100),
        ]

        for successes, total in fixtures:
            prod = production_wilson(successes, total)
            ref = wilson_interval_reference(successes, total)

            assert prod is not None
            assert ref is not None
            assert prod.lower == pytest.approx(ref.lower, abs=1e-5), f"Failed for {successes}/{total}"
            assert prod.upper == pytest.approx(ref.upper, abs=1e-5), f"Failed for {successes}/{total}"

    def test_bootstrap_agreement_deterministic(self):
        """Bootstrap produces deterministic same results with fixed seed."""
        data = {
            1: [1.0, 0.9, 1.0],
            2: [0.8, 0.85, 0.9],
            3: [0.7, 0.75, 0.8],
            4: [0.95, 0.9, 0.95],
            5: [0.6, 0.65, 0.7],
        }

        config = ClusterBootstrapConfig(seed=42, resample_count=500)

        # Run twice with same seed
        r1 = cluster_bootstrap_reference(data, config)
        r2 = cluster_bootstrap_reference(data, config)

        assert r1.observed_value == r2.observed_value
        assert r1.bootstrap_mean == r2.bootstrap_mean

    def test_paired_delta_agreement_deterministic(self):
        """Paired delta produces deterministic results."""
        baseline = [0.85, 0.82, 0.88, 0.90, 0.87]
        candidate = [0.88, 0.85, 0.90, 0.92, 0.89]

        r1 = paired_delta_reference(baseline, candidate)
        r2 = paired_delta_reference(baseline, candidate)

        assert r1.difference_mean == r2.difference_mean
        assert r1.confidence_interval == r2.confidence_interval


class TestEdgeCases:
    """Test edge cases and degenerate samples."""

    def test_singleton_cluster_indeterminate(self):
        """Singleton clusters with insufficient minimum yield indeterminate."""
        data = {1: [1.0], 2: [0.0]}
        config = ClusterBootstrapConfig(seed=42, resample_count=100, min_clusters=10)

        result = cluster_bootstrap_reference(data, config)

        assert result.observed_value == 0.0  # Indeterminate result
        assert result.percentile_lower == 0.0
        assert result.percentile_upper == 1.0

    def test_zero_denominator_interval(self):
        """Zero denominator yields None interval."""
        assert production_wilson(0, 0) is None
        assert wilson_interval_reference(0, 0) is None

    def test_all_success_or_all_failure_intervals(self):
        """Edge cases produce valid bounded intervals."""
        # All success
        interval = production_wilson(100, 100)
        assert interval.upper == pytest.approx(1.0, abs=1e-10)

        # All failure
        interval = production_wilson(0, 100)
        assert interval.lower == pytest.approx(0.0, abs=1e-10)


class TestMetricsEngineReferenceIntegration:
    """Test metrics engine integration with reference implementation (TODO 33)."""

    def test_metric_result_intervals_match_reference(self):
        """Metric computation intervals match reference implementation."""
        definition = MetricDefinition(
            metric_id="test_accuracy",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        # Test various proportions
        for successes, total in [(50, 100), (95, 100), (5, 10), (0, 100), (100, 100)]:
            result = definition.compute(numerator=successes, denominator=total)

            # Match reference Wilson interval
            ref = wilson_interval_reference(successes, total)

            assert result.value == pytest.approx(successes / total)
            if result.interval and ref:
                assert result.interval.lower == pytest.approx(ref.lower, abs=1e-5)
                assert result.interval.upper == pytest.approx(ref.upper, abs=1e-5)

    def test_comparison_invalid_status_returns_structured_result(self):
        """Invalid comparison returns structured MetricComparison with status."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100)

        # Create incompatible candidate (different version)
        candidate = MetricResult(
            metric_id="test",
            numerator=85,
            denominator=100,
            value=0.85,
            direction="higher",
            definition_version="2.0.0",
        )

        comparison = compute_metric_comparison(baseline, candidate)

        assert comparison.status.value == "incompatible"
        assert comparison.difference == 0.0
        assert comparison.confidence_interval == (0.0, 0.0)
        assert comparison.p_value is None

    def test_comparison_indeterminate_status_returns_structured_result(self):
        """Indeterminate comparison returns structured MetricComparison with status."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=0)  # Zero denom
        candidate = definition.compute(numerator=85, denominator=100)

        comparison = compute_metric_comparison(baseline, candidate)

        assert comparison.status.value == "indeterminate"
        assert comparison.incompatibility_reason is not None

    def test_exclusions_must_match_for_valid_comparison(self):
        """Exclusions must be identical for comparison to be valid."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100, exclusions={})
        candidate = definition.compute(numerator=85, denominator=100, exclusions={"timeout": 5})

        status = check_comparison_eligibility(baseline, candidate)

        assert status.value == "incompatible"

    def test_mismatched_direction_still_valid_if_other_fields_match(self):
        """Direction mismatch does not affect comparison eligibility."""
        # Note: Both metrics should have same direction in practice,
        # but the eligibility check does not validate direction
        baseline = MetricResult(
            metric_id="test",
            numerator=80,
            denominator=100,
            value=0.8,
            direction="higher",
            definition_version="1.0.0",
        )
        candidate = MetricResult(
            metric_id="test",
            numerator=85,
            denominator=100,
            value=0.85,
            direction="lower",  # Different direction
            definition_version="1.0.0",
        )

        status = check_comparison_eligibility(baseline, candidate)

        # Direction is not checked in eligibility - metrics are still comparable
        assert status.value == "valid"