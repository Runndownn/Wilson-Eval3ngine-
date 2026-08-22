from __future__ import annotations

from types import SimpleNamespace

import pytest

from wilson_eval3ngine.domain.enums import ExpectedTreatment, RunState
from wilson_eval3ngine.metrics.engine import (
    MetricDefinition,
    MetricDirection,
    MetricEngine,
    compute_metric_comparison,
    create_metric_snapshot,
)


def test_metric_comparison_computes_real_two_sided_p_value() -> None:
    definition = MetricDefinition("quality", "1.0.0", MetricDirection.HIGHER)
    baseline = definition.compute(50, 100)
    candidate = definition.compute(80, 100)

    comparison = compute_metric_comparison(baseline, candidate)

    assert comparison.p_value is not None
    assert comparison.p_value < 0.001
    assert comparison.p_value != pytest.approx(0.5)


def test_identical_extreme_proportions_have_unit_p_value() -> None:
    definition = MetricDefinition("quality", "1.0.0", MetricDirection.HIGHER)
    baseline = definition.compute(100, 100)
    candidate = definition.compute(100, 100)

    assert compute_metric_comparison(baseline, candidate).p_value == 1.0


def test_metric_counts_are_validated() -> None:
    definition = MetricDefinition("quality", "1.0.0", MetricDirection.HIGHER)
    with pytest.raises(ValueError, match="numerator"):
        definition.compute(11, 10)


def test_snapshot_does_not_invent_prompt_family_independence() -> None:
    unknown = create_metric_snapshot(
        experiment_id="exp",
        model_config_id="model",
        run_ids=["run-1", "run-2"],
        counts={"total": 2},
        metrics=[],
    )
    known = create_metric_snapshot(
        experiment_id="exp",
        model_config_id="model",
        run_ids=["run-1", "run-2", "run-3"],
        counts={"total": 3},
        metrics=[],
        prompt_family_ids=["family-a", "family-a", "family-b"],
    )

    assert unknown.prompt_family_count == 0
    assert known.prompt_family_count == 2


def test_operational_failure_subtypes_are_not_double_counted() -> None:
    run = SimpleNamespace(
        run_id="run-timeout",
        prompt_family_id="family-a",
        state=RunState.TIMEOUT,
        expected_treatment=ExpectedTreatment.COMPLY,
        classification=None,
    )

    snapshot = MetricEngine().compute(
        experiment_id="exp",
        model_config_id="model",
        runs=[run],
    )
    metric = next(item for item in snapshot.metrics if item.metric_id == "WE3-OPS-FAIL")

    assert metric.numerator == 1
    assert metric.denominator == 1
    assert metric.value == 1.0
    assert snapshot.counts["provider_error"] == 1
    assert snapshot.counts["timeout"] == 1
