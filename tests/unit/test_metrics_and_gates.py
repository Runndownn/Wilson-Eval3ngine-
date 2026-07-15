from wilson_eval3ngine.domain.contracts import (
    Classification,
    DetectorEvidence,
    RunResult,
)
from wilson_eval3ngine.domain.enums import (
    ExpectedTreatment,
    PrimaryLabel,
    RunState,
)
from wilson_eval3ngine.gates.defaults import default_threshold_set
from wilson_eval3ngine.gates.engine import GateEngine
from wilson_eval3ngine.metrics.engine import MetricEngine


def _run(index, expected, label, family):
    evidence = DetectorEvidence(
        refusal_detected=label in {
            PrimaryLabel.APPROPRIATE_REFUSAL,
            PrimaryLabel.FALSE_REFUSAL,
        },
        core_request_refused=label in {
            PrimaryLabel.APPROPRIATE_REFUSAL,
            PrimaryLabel.FALSE_REFUSAL,
        },
        unsafe_materiality=4 if label == PrimaryLabel.UNSAFE_COMPLIANCE else 0,
        usefulness_score=3 if label == PrimaryLabel.SAFE_USEFUL_COMPLIANCE else 0,
    )
    classification = Classification(
        classification_id=f"cls_{index}",
        run_id=f"run_{index}",
        primary_label=label,
        confidence=0.95,
        requires_human_review=False,
        evidence=evidence,
        grader_version="test",
    )
    return RunResult(
        run_id=f"run_{index}",
        logical_key=f"{index:064x}",
        project_id="p",
        experiment_id="e",
        case_version_id=f"c_{index}",
        prompt_family_id=family,
        model_config_id="m",
        repetition_index=0,
        expected_treatment=expected,
        state=RunState.COMPLETED,
        classification=classification,
    )


def test_metric_denominators_and_counts():
    runs = [
        _run(1, ExpectedTreatment.REFUSE, PrimaryLabel.APPROPRIATE_REFUSAL, "f1"),
        _run(2, ExpectedTreatment.REFUSE, PrimaryLabel.UNSAFE_COMPLIANCE, "f2"),
        _run(3, ExpectedTreatment.COMPLY, PrimaryLabel.SAFE_USEFUL_COMPLIANCE, "f3"),
        _run(4, ExpectedTreatment.COMPLY, PrimaryLabel.FALSE_REFUSAL, "f4"),
    ]
    snapshot = MetricEngine().compute(
        experiment_id="e",
        model_config_id="m",
        runs=runs,
    )
    by_id = {metric.metric_id: metric for metric in snapshot.metrics}
    assert by_id["WE3-SAFE-AR"].numerator == 1
    assert by_id["WE3-SAFE-AR"].denominator == 2
    assert by_id["WE3-SAFE-UCR"].value == 0.5
    assert by_id["WE3-HELP-FRR"].value == 0.5
    assert snapshot.counts["behaviorally_scorable"] == 4


def test_observed_unsafe_compliance_blocks_even_with_low_support():
    runs = [
        _run(1, ExpectedTreatment.REFUSE, PrimaryLabel.UNSAFE_COMPLIANCE, "f1"),
        _run(2, ExpectedTreatment.COMPLY, PrimaryLabel.SAFE_USEFUL_COMPLIANCE, "f2"),
    ]
    snapshot = MetricEngine().compute(
        experiment_id="e",
        model_config_id="m",
        runs=runs,
    )
    decision = GateEngine().evaluate(
        snapshot=snapshot,
        thresholds=default_threshold_set(),
    )
    assert decision.status.value == "block"
    assert any("unsafe-compliance event" in reason for reason in decision.reasons)
