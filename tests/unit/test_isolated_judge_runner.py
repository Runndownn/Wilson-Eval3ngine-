"""
Tests for Isolated Schema-Only Judge Runner (TODO 30).

Tests security boundaries, schema validation, and isolation guarantees.
"""

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


class TestJudgeInputBundle:
    """Test input bundle creation and integrity."""

    def test_bundle_separation(self) -> None:
        """Input bundle separates trusted and untrusted content."""
        response = ProviderResponse(
            run_id="run_test",
            attempt_id="att_test",
            protocol_valid=True,
            terminal=True,
            text="Test response content",
            provider_reported_model="mock",
        )
        
        expectation = ExpectationRecord(
            expectation_id="exp_test",
            case_version_id="case_test",
            expected_treatment=ExpectedTreatment.COMPLY,
            required_concepts=[],
            prohibited_behavior=[],
            minimum_usefulness=2,
            materiality_floor=2,
            policy_version_id="pol_1",
            rubric_version_id="rub_1",
            rule_version="1.0.0",
            source_case_hash="hash",
        )
        
        runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
        bundle = runner.create_input_bundle("run_test", expectation, response)
        
        # Bundle should have separate hashes
        assert bundle.expectation_hash != bundle.response_hash
        
        # Evidence segments should be labeled as untrusted
        assert bundle.evidence_segments[0].segment_type == "response"
        assert bundle.evidence_segments[0].segment_hash is not None

    def test_bundle_deterministic_hash(self) -> None:
        """Bundle hash should be deterministic for same inputs."""
        response = ProviderResponse(
            run_id="run_test",
            attempt_id="att_test",
            protocol_valid=True,
            terminal=True,
            text="Deterministic content",
            provider_reported_model="mock",
        )
        
        expectation = ExpectationRecord(
            expectation_id="exp_test",
            case_version_id="case_test",
            expected_treatment=ExpectedTreatment.COMPLY,
            required_concepts=[],
            prohibited_behavior=[],
            minimum_usefulness=2,
            materiality_floor=2,
            policy_version_id="pol_1",
            rubric_version_id="rub_1",
            rule_version="1.0.0",
            source_case_hash="hash",
        )
        
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        
        bundle1 = runner.create_input_bundle("run_test", expectation, response)
        bundle2 = runner.create_input_bundle("run_test", expectation, response)
        
        assert bundle1.content_hash() == bundle2.content_hash()


class TestStrictOutputSchema:
    """Test strict output schema validation."""

    def test_valid_output_accepts(self) -> None:
        """Valid output passes schema validation."""
        valid_output = {
            "primary_label": "safe_useful_compliance",
            "secondary_labels": [],
            "confidence": 0.95,
            "abstention": False,
            "evidence_references": ["hash1"],
            "reason_codes": ["rule_1"],
        }
        
        result = StrictOutputSchema.validate(valid_output)
        assert result == valid_output

    def test_unknown_fields_rejected(self) -> None:
        """Unknown fields are rejected to prevent injection."""
        output_with_injection = {
            "primary_label": "safe_useful_compliance",
            "secondary_labels": [],
            "confidence": 0.95,
            "abstention": False,
            "evidence_references": ["hash1"],
            "reason_codes": ["rule_1"],
            "malicious_field": "injected content",
        }
        
        with pytest.raises(ValueError, match="Unknown output fields"):
            StrictOutputSchema.validate(output_with_injection)

    def test_invalid_primary_label_rejected(self) -> None:
        """Invalid primary label is rejected."""
        output_with_bad_label = {
            "primary_label": "not_a_valid_label",
            "secondary_labels": [],
            "confidence": 0.95,
            "abstention": False,
            "evidence_references": [],
            "reason_codes": [],
        }
        
        with pytest.raises(ValueError, match="Invalid primary_label"):
            StrictOutputSchema.validate(output_with_bad_label)

    def test_invalid_confidence_rejected(self) -> None:
        """Confidence outside 0-1 range is rejected."""
        output_with_bad_confidence = {
            "primary_label": "safe_useful_compliance",
            "secondary_labels": [],
            "confidence": 1.5,
            "abstention": False,
            "evidence_references": [],
            "reason_codes": [],
        }
        
        with pytest.raises(ValueError, match="Confidence must be"):
            StrictOutputSchema.validate(output_with_bad_confidence)


class TestJudgeIsolation:
    """Test judge isolation boundaries."""

    def test_verify_network_disabled(self) -> None:
        """Judge runner reports no network access."""
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        isolation = runner.verify_isolation()
        
        assert isolation["network_disabled"] is True

    def test_verify_tools_unavailable(self) -> None:
        """Judge runner reports no tool capabilities."""
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        isolation = runner.verify_isolation()
        
        assert isolation["tools_unavailable"] is True

    def test_verify_credentials_absent(self) -> None:
        """Judge runner cannot access provider credentials."""
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        isolation = runner.verify_isolation()
        
        assert isolation["credentials_absent"] is True

    def test_verify_filesystem_readonly(self) -> None:
        """Judge runner uses read-only filesystem."""
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        isolation = runner.verify_isolation()
        
        assert isolation["filesystem_readonly"] is True


class TestJudgeExecution:
    """Test judge execution with evidence validation."""

    def test_execute_judge_returns_valid_output(self) -> None:
        """Judge execution returns schema-valid output."""
        response = ProviderResponse(
            run_id="run_test",
            attempt_id="att_test",
            protocol_valid=True,
            terminal=True,
            text="Safe helpful response content.",
            provider_reported_model="mock",
        )
        
        expectation = ExpectationRecord(
            expectation_id="exp_test",
            case_version_id="case_test",
            expected_treatment=ExpectedTreatment.COMPLY,
            required_concepts=[],
            prohibited_behavior=[],
            minimum_usefulness=2,
            materiality_floor=2,
            policy_version_id="pol_1",
            rubric_version_id="rub_1",
            rule_version="1.0.0",
            source_case_hash="hash",
        )
        
        runner = IsolatedJudgeRunner(rubric_content="Trusted rubric")
        bundle = runner.create_input_bundle("run_test", expectation, response)
        
        result = runner.execute_judge(bundle)
        
        # Result should have required fields
        assert "primary_label" in result
        assert "confidence" in result
        assert "abstention" in result
        assert "evidence_references" in result

    def test_unsafe_content_detected(self) -> None:
        """Judge detects unsafe content in evidence."""
        response = ProviderResponse(
            run_id="run_unsafe",
            attempt_id="att_unsafe",
            protocol_valid=True,
            terminal=True,
            text="[WE3_UNSAFE_MATERIAL] Dangerous content here.",
            provider_reported_model="mock",
        )
        
        expectation = ExpectationRecord(
            expectation_id="exp_unsafe",
            case_version_id="case_unsafe",
            expected_treatment=ExpectedTreatment.REFUSE,
            required_concepts=[],
            prohibited_behavior=[],
            minimum_usefulness=2,
            materiality_floor=2,
            policy_version_id="pol_1",
            rubric_version_id="rub_1",
            rule_version="1.0.0",
            source_case_hash="hash",
        )
        
        runner = IsolatedJudgeRunner(rubric_content="Rubric")
        bundle = runner.create_input_bundle("run_unsafe", expectation, response)
        
        result = runner.execute_judge(bundle)
        
        assert result["primary_label"] == "unsafe_compliance"

    def test_evidence_references_validated(self) -> None:
        """Evidence references must be valid hashes."""
        available = {"hash1", "hash2", "hash3"}
        
        # Valid references
        valid = validate_evidence_references(["hash1", "hash2"], available)
        assert len(valid) == 2
        
        # Invalid references raise
        with pytest.raises(ValueError, match="Invalid evidence references"):
            validate_evidence_references(["hash1", "invalid_hash"], available)


class TestJudgeFactory:
    """Test judge runner factory."""

    def test_factory_creates_isolated_runner(self) -> None:
        """Factory creates properly configured isolated runner."""
        runner = JudgeRunnerFactory.create_runner(
            rubric_ref="artifact://rubrics/security_behavior_1.0.0",
        )
        
        assert isinstance(runner, IsolatedJudgeRunner)
        assert runner.max_runtime_seconds == 60

    def test_factory_rubric_cache(self) -> None:
        """Factory caches rubric content for efficiency."""
        runner1 = JudgeRunnerFactory.create_runner("artifact://test/rubric")
        runner2 = JudgeRunnerFactory.create_runner("artifact://test/rubric")
        
        # Same rubric reference should use cached content
        assert runner1.rubric_content == runner2.rubric_content


class TestEvidenceSegment:
    """Test evidence segment handling."""

    def test_segment_from_response(self) -> None:
        """Evidence segment created from response."""
        response = ProviderResponse(
            run_id="run_seg",
            attempt_id="att_seg",
            protocol_valid=True,
            terminal=True,
            text="Segment content",
            provider_reported_model="mock",
        )
        
        segment = EvidenceSegment.from_response(response)
        
        assert segment.segment_type == "response"
        assert segment.content == "Segment content"
        assert segment.mime_type == "text/plain"

    def test_injection_content_inert(self) -> None:
        """Injection attempts in evidence are inert."""
        response = ProviderResponse(
            run_id="run_inject",
            attempt_id="att_inject",
            protocol_valid=True,
            terminal=True,
            text="<script>malicious()</script>",
            provider_reported_model="mock",
        )
        
        segment = EvidenceSegment.from_response(response)
        
        # Content is stored as-is, inert text
        assert "<script>" in segment.content
        # No execution occurred