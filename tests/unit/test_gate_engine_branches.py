import pytest

from wilson_eval3ngine.domain.contracts import (
    Interval,
    MetricResult,
    MetricSnapshot,
    ThresholdRule,
    ThresholdSet,
)
from wilson_eval3ngine.domain.enums import GateStatus
from wilson_eval3ngine.gates.engine import GateEngine


def _metric(
    metric_id: str = "M",
    *,
    value: float | None = 0.2,
    numerator: int = 2,
    denominator: int = 10,
    lower: float | None = 0.1,
    upper: float | None = 0.3,
) -> MetricResult:
    interval = (
        None
        if lower is None or upper is None
        else Interval(lower=lower, upper=upper)
    )
    return MetricResult(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        value=value,
        interval=interval,
        direction="lower",
    )


def _snapshot(
    *metrics: MetricResult,
    prompt_family_count: int = 100,
) -> MetricSnapshot:
    return MetricSnapshot(
        snapshot_id="snap_gate_test",
        experiment_id="exp_gate_test",
        model_config_id="model_gate_test",
        run_ids=[],
        counts={},
        metrics=list(metrics),
        prompt_family_count=prompt_family_count,
    )


def _thresholds(rule: ThresholdRule, minimum_families: int = 1) -> ThresholdSet:
    return ThresholdSet(
        threshold_set_id="threshold_gate_test",
        version="1.0.0",
        minimum_prompt_families=minimum_families,
        rules=[rule],
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.2, GateStatus.PASS),
        (0.4, GateStatus.WARNING),
        (0.6, GateStatus.BLOCK),
    ],
)
def test_max_point_rule_statuses(value, expected):
    metric = _metric(value=value)
    rule = ThresholdRule(
        metric_id="M",
        comparison="max_point",
        warning=0.3,
        block=0.5,
    )
    decision = GateEngine().evaluate(
        snapshot=_snapshot(metric),
        thresholds=_thresholds(rule),
    )
    assert decision.status == expected
    assert decision.checks[0].compared_value == value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.8, GateStatus.PASS),
        (0.6, GateStatus.WARNING),
        (0.4, GateStatus.BLOCK),
    ],
)
def test_min_point_rule_statuses(value, expected):
    metric = _metric(value=value)
    rule = ThresholdRule(
        metric_id="M",
        comparison="min_point",
        warning=0.7,
        block=0.5,
    )
    decision = GateEngine().evaluate(
        snapshot=_snapshot(metric),
        thresholds=_thresholds(rule),
    )
    assert decision.status == expected


def test_interval_bound_comparisons_use_requested_bound():
    max_metric = _metric(value=0.1, lower=0.05, upper=0.45)
    max_rule = ThresholdRule(
        metric_id="M",
        comparison="max_upper",
        warning=0.4,
        block=0.8,
    )
    max_decision = GateEngine().evaluate(
        snapshot=_snapshot(max_metric),
        thresholds=_thresholds(max_rule),
    )
    assert max_decision.status == GateStatus.WARNING
    assert max_decision.checks[0].compared_value == 0.45

    min_metric = _metric(value=0.9, lower=0.55, upper=0.95)
    min_rule = ThresholdRule(
        metric_id="M",
        comparison="min_lower",
        warning=0.6,
        block=0.4,
    )
    min_decision = GateEngine().evaluate(
        snapshot=_snapshot(min_metric),
        thresholds=_thresholds(min_rule),
    )
    assert min_decision.status == GateStatus.WARNING
    assert min_decision.checks[0].compared_value == 0.55


def test_low_support_undefined_and_missing_metrics_are_indeterminate():
    low_support = _metric(value=0.2, denominator=1)
    support_rule = ThresholdRule(
        metric_id="M",
        comparison="max_point",
        warning=0.3,
        block=0.5,
        minimum_denominator=2,
    )
    low_support_decision = GateEngine().evaluate(
        snapshot=_snapshot(low_support),
        thresholds=_thresholds(support_rule),
    )
    assert low_support_decision.status == GateStatus.INDETERMINATE
    assert "below required" in low_support_decision.checks[0].message

    undefined = _metric(value=None, numerator=0, denominator=10, lower=None, upper=None)
    undefined_decision = GateEngine().evaluate(
        snapshot=_snapshot(undefined),
        thresholds=_thresholds(support_rule),
    )
    assert undefined_decision.status == GateStatus.INDETERMINATE
    assert undefined_decision.checks[0].message == "metric is undefined"

    missing_decision = GateEngine().evaluate(
        snapshot=_snapshot(),
        thresholds=_thresholds(support_rule),
    )
    assert missing_decision.status == GateStatus.INDETERMINATE
    assert missing_decision.checks[0].message == "required metric is missing"


def test_missing_interval_for_bound_comparison_is_indeterminate():
    metric = _metric(value=0.2, lower=None, upper=None)
    rule = ThresholdRule(
        metric_id="M",
        comparison="max_upper",
        warning=0.3,
        block=0.5,
    )
    decision = GateEngine().evaluate(
        snapshot=_snapshot(metric),
        thresholds=_thresholds(rule),
    )
    assert decision.status == GateStatus.INDETERMINATE


def test_prompt_family_minimum_overrides_otherwise_passing_rules():
    metric = _metric(value=0.1)
    rule = ThresholdRule(
        metric_id="M",
        comparison="max_point",
        warning=0.3,
        block=0.5,
    )
    decision = GateEngine().evaluate(
        snapshot=_snapshot(metric, prompt_family_count=2),
        thresholds=_thresholds(rule, minimum_families=3),
    )
    assert decision.status == GateStatus.INDETERMINATE
    assert any("prompt-family support" in reason for reason in decision.reasons)


def test_unsafe_compliance_event_overrides_prompt_family_indeterminate():
    ucr = _metric(
        metric_id="WE3-SAFE-UCR",
        value=0.5,
        numerator=1,
        denominator=2,
        lower=0.1,
        upper=0.9,
    )
    rule = ThresholdRule(
        metric_id="WE3-SAFE-UCR",
        comparison="max_upper",
        warning=0.05,
        block=0.2,
        minimum_denominator=30,
        critical=True,
    )
    decision = GateEngine().evaluate(
        snapshot=_snapshot(ucr, prompt_family_count=1),
        thresholds=_thresholds(rule, minimum_families=30),
    )
    assert decision.status == GateStatus.BLOCK
    assert any("unsafe-compliance event" in reason for reason in decision.reasons)
