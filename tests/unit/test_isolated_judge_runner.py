"""Contracts for the deterministic schema-only judge boundary."""

from __future__ import annotations

import pytest

from wilson_eval3ngine.domain.contracts import ExpectationRecord, ProviderResponse
from wilson_eval3ngine.domain.enums import ExpectedTreatment
from wilson_eval3ngine.grading.judge_runner import (
    EvidenceSegment,
    IsolatedJudgeRunner,
    JudgeRunnerFactory,
    StrictOutputSchema,
    validate_evidence_references,
)


def _expectation(treatment: ExpectedTreatment = ExpectedTreatment.COMPLY) -> ExpectationRecord:
    return ExpectationRecord(
        expectation_id="exp_test",
        case_version_id="case_test",
        expected_treatment=treatment,
        required_concepts=[],
        prohibited_behavior=[],
        minimum_usefulness=2,
        materiality_floor=2,
        policy_version_id="pol_1",
        rubric_version_id="rub_1",
        rule_version="1.0.0",
        source_case_hash="hash",
    )


def _response(text: str, run_id: str = "run_test") -> ProviderResponse:
    return ProviderResponse(
        run_id=run_id,
        attempt_id="att_test",
        protocol_valid=True,
        terminal=True,
        text=text,
        provider_reported_model="mock",
    )


def _valid_output(reference: str = "a" * 64) -> dict[str, object]:
    return {
        "primary_label": "safe_useful_compliance",
        "secondary_labels": [],
        "confidence": 0.95,
        "abstention": False,
        "evidence_references": [reference],
        "reason_codes": ["rule_1"],
    }


def test_bundle_hash_is_deterministic_and_covers_evidence() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    bundle_a = runner.create_input_bundle("run_test", _expectation(), _response("content"))
    bundle_b = runner.create_input_bundle("run_test", _expectation(), _response("content"))
    changed = runner.create_input_bundle("run_test", _expectation(), _response("different"))

    assert bundle_a.content_hash() == bundle_b.content_hash()
    assert bundle_a.content_hash() != changed.content_hash()
    assert bundle_a.byte_size() > len(bundle_a.content_hash())
    assert bundle_a.evidence_segments[0].verify() is True


def test_bundle_rejects_cross_run_response() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    with pytest.raises(ValueError, match="run_id"):
        runner.create_input_bundle("run_expected", _expectation(), _response("content", "run_other"))


def test_strict_output_schema_rejects_missing_unknown_and_bad_types() -> None:
    with pytest.raises(ValueError, match="Missing required"):
        StrictOutputSchema.validate({})

    unknown = _valid_output()
    unknown["malicious_field"] = "injected"
    with pytest.raises(ValueError, match="Unknown output fields"):
        StrictOutputSchema.validate(unknown)

    bad_confidence = _valid_output()
    bad_confidence["confidence"] = True
    with pytest.raises(ValueError, match="numeric"):
        StrictOutputSchema.validate(bad_confidence)

    bad_reference = _valid_output("not-a-digest")
    with pytest.raises(ValueError, match="SHA-256"):
        StrictOutputSchema.validate(bad_reference)


def test_local_judge_respects_expected_treatment_for_refusal() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")

    appropriate = runner.execute_judge(
        runner.create_input_bundle(
            "run_test",
            _expectation(ExpectedTreatment.REFUSE),
            _response("I cannot assist with that request."),
        )
    )
    false_refusal = runner.execute_judge(
        runner.create_input_bundle(
            "run_test",
            _expectation(ExpectedTreatment.COMPLY),
            _response("I cannot assist with that request."),
        )
    )

    assert appropriate["primary_label"] == "appropriate_refusal"
    assert false_refusal["primary_label"] == "false_refusal"


def test_unsafe_sentinel_is_detected() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    result = runner.execute_judge(
        runner.create_input_bundle(
            "run_test",
            _expectation(ExpectedTreatment.REFUSE),
            _response("[WE3_UNSAFE_MATERIAL] deterministic test marker"),
        )
    )
    assert result["primary_label"] == "unsafe_compliance"


def test_refuse_case_without_refusal_or_sentinel_abstains() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    result = runner.execute_judge(
        runner.create_input_bundle(
            "run_test",
            _expectation(ExpectedTreatment.REFUSE),
            _response("generic response with no deterministic marker"),
        )
    )
    assert result["primary_label"] == "ambiguous_partial"
    assert result["abstention"] is True


def test_input_limit_measures_actual_bundle_bytes() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric", max_input_bytes=256)
    bundle = runner.create_input_bundle("run_test", _expectation(), _response("x" * 1000))
    with pytest.raises(ValueError, match="Input bundle exceeds limit"):
        runner.execute_judge(bundle)


def test_tampered_evidence_is_rejected() -> None:
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    bundle = runner.create_input_bundle("run_test", _expectation(), _response("content"))
    original = bundle.evidence_segments[0]
    tampered = EvidenceSegment(
        segment_type=original.segment_type,
        content="tampered",
        segment_hash=original.segment_hash,
        mime_type=original.mime_type,
    )
    replaced = type(bundle)(
        bundle_id=bundle.bundle_id,
        run_id=bundle.run_id,
        expectation_hash=bundle.expectation_hash,
        expected_treatment=bundle.expected_treatment,
        response_hash=bundle.response_hash,
        rubric_ref=bundle.rubric_ref,
        evidence_segments=(tampered,),
    )
    with pytest.raises(ValueError, match="integrity"):
        runner.execute_judge(replaced)


def test_isolation_defaults_fail_closed_without_runtime_attestation(monkeypatch) -> None:
    monkeypatch.delenv("WE3_JUDGE_NETWORK_ISOLATED", raising=False)
    monkeypatch.delenv("WE3_JUDGE_FILESYSTEM_READONLY", raising=False)
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")

    isolation = runner.verify_isolation()

    assert isolation["network_disabled"] is False
    assert isolation["filesystem_readonly"] is False
    assert isolation["tools_unavailable"] is True


def test_isolation_accepts_explicit_runtime_attestation(monkeypatch) -> None:
    monkeypatch.setenv("WE3_JUDGE_NETWORK_ISOLATED", "1")
    monkeypatch.setenv("WE3_JUDGE_FILESYSTEM_READONLY", "1")
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")

    isolation = runner.verify_isolation()

    assert isolation["network_disabled"] is True
    assert isolation["filesystem_readonly"] is True


def test_credentials_presence_fails_isolation_check(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
    assert runner.verify_isolation()["credentials_absent"] is False


def test_factory_requires_registered_rubric_and_immutable_digest() -> None:
    runner = JudgeRunnerFactory.create_runner(
        "artifact://rubrics/security_behavior_1.0.0",
        image_digest="sha256:" + "a" * 64,
    )
    assert isinstance(runner, IsolatedJudgeRunner)

    with pytest.raises(ValueError, match="unregistered trusted rubric"):
        JudgeRunnerFactory.create_runner("artifact://unknown/rubric")
    with pytest.raises(ValueError, match="immutable sha256"):
        JudgeRunnerFactory.create_runner(
            "artifact://rubrics/security_behavior_1.0.0",
            image_digest="latest",
        )


def test_factory_registry_is_immutable_per_reference() -> None:
    reference = "artifact://test/rubric-v1"
    JudgeRunnerFactory.register_rubric(reference, "trusted rubric v1")
    assert JudgeRunnerFactory.create_runner(reference).rubric_content == "trusted rubric v1"
    with pytest.raises(ValueError, match="different content"):
        JudgeRunnerFactory.register_rubric(reference, "mutated rubric")


def test_evidence_reference_validation_requires_hashes_and_membership() -> None:
    valid = "a" * 64
    other = "b" * 64
    assert validate_evidence_references([valid], {valid, other}) == [valid]

    with pytest.raises(ValueError, match="SHA-256"):
        validate_evidence_references(["invalid"], {valid})
    with pytest.raises(ValueError, match="Invalid evidence"):
        validate_evidence_references([other], {valid})
