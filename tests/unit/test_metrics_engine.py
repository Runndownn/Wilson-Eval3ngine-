"""Unit tests for versioned metrics engine (TODO 33).

Tests cover:
- MetricRegistry with definitions
- MetricResult computation with intervals
- Comparison eligibility checks
- Drift detection
- Snapshot creation
"""

import pytest

from wilson_eval3ngine.domain.contracts import MetricResult
from wilson_eval3ngine.metrics.engine import (
    ComparisonStatus,
    MetricDefinition,
    MetricDirection,
    check_comparison_eligibility,
    compute_metric_comparison,
    create_metric_snapshot,
    default_metric_registry,
    detect_metric_drift,
)


class TestMetricDefinition:
    """Test metric definition computation."""

    def test_compute_proportion_metric(self):
        """Basic proportion metric computation."""
        definition = MetricDefinition(
            metric_id="test_metric",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        result = definition.compute(numerator=85, denominator=100)

        assert isinstance(result, MetricResult)
        assert result.metric_id == "test_metric"
        assert result.value == 0.85
        assert result.interval is not None
        assert 0.75 < result.interval.lower < 0.85
        assert 0.85 < result.interval.upper < 0.95

    def test_compute_zero_denominator(self):
        """Zero denominator yields None value and interval."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        result = definition.compute(numerator=0, denominator=0)

        assert result.value is None
        assert result.interval is None


class TestMetricRegistry:
    """Test metric registry functionality."""

    def test_default_registry_has_core_metrics(self):
        """Default registry includes core safety metrics."""
        registry = default_metric_registry()

        assert registry.get("safe_useful_compliance_rate") is not None
        assert registry.get("unsafe_compliance_recall") is not None
        assert registry.get("false_refusal_rate") is not None
        assert registry.get("protocol_valid_rate") is not None

    def test_compute_metric_by_id(self):
        """Compute metric by ID from registry."""
        registry = default_metric_registry()

        result = registry.compute_metric(
            metric_id="safe_useful_compliance_rate",
            numerator=90,
            denominator=100,
        )

        assert result.metric_id == "safe_useful_compliance_rate"
        assert result.value == 0.9

    def test_unknown_metric_raises(self):
        """Unknown metric ID raises error."""
        registry = default_metric_registry()

        with pytest.raises(ValueError):
            registry.compute_metric("unknown_metric", 10, 100)


class TestComparisonEligibility:
    """Test comparison eligibility checks."""

    def test_compatible_metrics_valid(self):
        """Compatible metrics yield valid status."""
        definition = MetricDefinition(
            metric_id="test_metric",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100)
        candidate = definition.compute(numerator=85, denominator=100)

        status = check_comparison_eligibility(baseline, candidate)

        assert status == ComparisonStatus.VALID

    def test_mismatched_version_incompatible(self):
        """Different versions are incompatible."""
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
            direction="higher",
            definition_version="2.0.0",
        )

        status = check_comparison_eligibility(baseline, candidate)

        assert status == ComparisonStatus.INCOMPATIBLE

    def test_zero_denominator_indeterminate(self):
        """Zero denominator yields indeterminate."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )
        baseline = definition.compute(numerator=0, denominator=0)

        status = check_comparison_eligibility(baseline, baseline)

        assert status == ComparisonStatus.INDETERMINATE

    def test_mismatched_metric_id_incompatible(self):
        """Different metric IDs are incompatible."""
        definition = MetricDefinition(
            metric_id="test_metric",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100)
        # Create with different metric_id
        candidate = MetricResult(
            metric_id="different_metric",
            numerator=85,
            denominator=100,
            value=0.85,
            direction="higher",
            definition_version="1.0.0",
        )

        status = check_comparison_eligibility(baseline, candidate)

        assert status == ComparisonStatus.INCOMPATIBLE

    def test_mismatched_exclusions_incompatible(self):
        """Different exclusions make comparison incompatible."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100, exclusions={"timeout": 5})
        candidate = definition.compute(numerator=85, denominator=100, exclusions={"timeout": 3})

        status = check_comparison_eligibility(baseline, candidate)

        assert status == ComparisonStatus.INCOMPATIBLE

    def test_same_empty_exclusions_valid(self):
        """Same empty exclusions yield valid status."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=80, denominator=100, exclusions={})
        candidate = definition.compute(numerator=85, denominator=100, exclusions={})

        status = check_comparison_eligibility(baseline, candidate)

        assert status == ComparisonStatus.VALID


class TestMetricComparison:
    """Test metric comparison computation."""

    def test_comparison_computes_difference(self):
        """Comparison computes value difference."""
        definition = MetricDefinition(
            metric_id="test",
            version="1.0.0",
            direction=MetricDirection.HIGHER,
        )

        baseline = definition.compute(numerator=70, denominator=100)
        candidate = definition.compute(numerator=80, denominator=100)

        comparison = compute_metric_comparison(baseline, candidate)

        assert comparison.status == ComparisonStatus.VALID
        assert comparison.difference == pytest.approx(0.1)


class TestDriftDetection:
    """Test drift detection functionality."""

    def test_detect_significant_drift(self):
        """Significant drift detected when threshold exceeded."""
        baseline = {"accuracy": 0.90, "latency": 0.5}
        candidate = {"accuracy": 0.75, "latency": 0.6}  # 16.7% drop in accuracy

        indicators = detect_metric_drift(baseline, candidate, threshold=0.1)

        accuracy_drift = next(i for i in indicators if i.metric_id == "accuracy")
        assert accuracy_drift.significant is True


class TestMetricSnapshot:
    """Test immutable metric snapshot creation."""

    def test_snapshot_has_content_hash(self):
        """Snapshot computes SHA-256 content hash."""
        snapshot = create_metric_snapshot(
            experiment_id="exp_001",
            model_config_id="model_test",
            run_ids=["run_1", "run_2"],
            counts={"total": 2},
            metrics=[],
        )

        assert snapshot.snapshot_sha256 is not None
        assert len(snapshot.snapshot_sha256) == 64  # SHA-256 hex length


class TestMetricDirection:
    """Test metric direction enum."""

    def test_direction_values(self):
        """All direction values are valid."""
        assert MetricDirection.HIGHER.value == "higher"
        assert MetricDirection.LOWER.value == "lower"
        assert MetricDirection.DESCRIPTIVE.value == "descriptive"