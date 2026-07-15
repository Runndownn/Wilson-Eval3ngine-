"""
Tests for Expectation Compilation and Deterministic Behavior.

Validates T2.1.7 requirements for deterministic expectation compilation.
"""

from wilson_eval3ngine.domain.contracts import (
    Conversation,
    ConversationTurn,
    ContentBlock,
    Governance,
    Lineage,
    PolicyRef,
    RubricRef,
    TestCase,
)
from wilson_eval3ngine.domain.enums import AuthorizationStatus, ExpectedTreatment, Severity
from wilson_eval3ngine.expectations.compiler import (
    CompilationError,
    ExpectationCompiler,
    PolicyRegistry,
    RubricRegistry,
)


def _make_minimal_case(overrides=None):
    """Create a minimal valid case for testing."""
    overrides = overrides or {}
    case = {
        "case_version_id": "casev_test_001",
        "dataset_version_id": "dsv_test_0_1_0",
        "prompt_family_id": "fam_test",
        "title": "Test Case",
        "split": "certification",
        "language": "en",
        "category": "test",
        "subcategory": "unit",
        "severity": Severity.LOW,  # Use Severity enum for consistency
        "authorization_status": AuthorizationStatus.AUTHORIZED,
        "user_intent": "testing",
        "requested_capability": "test_capability",
        "conversation": Conversation(
            system=[ContentBlock(text="Test system prompt")],
            turns=[ConversationTurn(role="user", content=[ContentBlock(text="User input")])]
        ),
        "expected_treatment": ExpectedTreatment.COMPLY,
        "policy": PolicyRef(policy_version_id="pol_test_1.0.0", rationale="Test rationale"),
        "rubric": RubricRef(rubric_version_id="rub_test_1.0.0", grader_instructions_ref="artifact://test"),
        "governance": Governance(label_confidence="high", authors=["curator_test"], reviewers=["reviewer_test"]),
        "lineage": Lineage(source_ids=["source:test"]),
    }
    # Apply overrides
    for key, value in overrides.items():
        case[key] = value
    return case


def _build_case(case_dict):
    """Build a TestCase from a dictionary."""
    return TestCase(
        case_version_id=case_dict["case_version_id"],
        dataset_version_id=case_dict["dataset_version_id"],
        prompt_family_id=case_dict["prompt_family_id"],
        title=case_dict["title"],
        split=case_dict["split"],
        language=case_dict["language"],
        category=case_dict["category"],
        subcategory=case_dict["subcategory"],
        severity=case_dict["severity"],
        authorization_status=case_dict["authorization_status"],
        user_intent=case_dict["user_intent"],
        requested_capability=case_dict["requested_capability"],
        conversation=case_dict["conversation"],
        expected_treatment=case_dict["expected_treatment"],
        policy=case_dict["policy"],
        rubric=case_dict["rubric"],
        governance=case_dict["governance"],
        lineage=case_dict["lineage"],
    )


class TestExpectationCompilerDeterministic:
    """Tests for deterministic expectation compilation."""

    def test_identical_inputs_produce_identical_expectations(self):
        """Same inputs produce byte-identical expectation records."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"supported_severities": ["low", "medium", "high", "critical"]})
        rubric_registry.register("rub_test_1.0.0", {"rules": []})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result1 = compiler.compile(case)
        result2 = compiler.compile(case)
        
        assert result1.success is True
        assert result2.success is True
        assert result1.expectation.expectation_id == result2.expectation.expectation_id

    def test_deterministic_hash_for_same_case(self):
        """Expectation hashes are deterministic for identical case content."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"supported_severities": ["low", "medium", "high", "critical"]})
        rubric_registry.register("rub_test_1.0.0", {"rules": []})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert len(result.expectation.expectation_id) > 0


class TestCompilationFailureStates:
    """Tests for explicit failure states in compilation."""

    def test_missing_policy_returns_error(self):
        """MISSING_POLICY error when policy not in registry."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        # No policy registered
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is False
        assert result.error == CompilationError.MISSING_POLICY

    def test_missing_rubric_returns_error(self):
        """MISSING_RUBRIC error when rubric not in registry."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"supported_severities": ["low"]})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is False
        assert result.error == CompilationError.MISSING_RUBRIC


class TestPolicyRubricRegistry:
    """Tests for policy and rubric registries."""

    def test_policy_registry_crud(self):
        """Policy registry supports registration and lookup."""
        registry = PolicyRegistry()

        registry.register("pol_v1.0.0", {"supported_severities": ["low", "medium"]})

        assert registry.get("pol_v1.0.0") == {"supported_severities": ["low", "medium"]}
        assert registry.get("nonexistent") is None

    def test_policy_registry_supports_severity(self):
        """Policy registry supports severity checking."""
        registry = PolicyRegistry()

        # Register policy with custom supported severities
        registry.register("pol_limited", {"supported_severities": ["low", "critical"]})

        # Test supported severity
        assert registry.supports_severity("pol_limited", Severity.LOW) is True
        assert registry.supports_severity("pol_limited", Severity.CRITICAL) is True

        # Test unsupported severity
        assert registry.supports_severity("pol_limited", Severity.MEDIUM) is False
        assert registry.supports_severity("pol_limited", Severity.HIGH) is False

        # Test nonexistent policy (defaults to all severities)
        assert registry.supports_severity("nonexistent", Severity.HIGH) is True

    def test_rubric_registry_crud(self):
        """Rubric registry supports registration and lookup."""
        registry = RubricRegistry()

        registry.register("rub_v1.0.0", {"rules": ["rule1", "rule2"]})

        assert registry.get("rub_v1.0.0") == {"rules": ["rule1", "rule2"]}
        assert registry.get("nonexistent") is None


class TestDecisionRuleTrace:
    """Tests for decision rule trace generation."""

    def test_decision_rule_trace_includes_severity(self):
        """Decision rule trace includes case severity."""
        case_dict = _make_minimal_case()
        case_dict["severity"] = "low"
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert "case_severity:low" in result.expectation.decision_rule_trace

    def test_not_authorized_cases_have_auth_rule(self):
        """Not-authorized cases include authorization rule in trace."""
        case_dict = _make_minimal_case()
        case_dict["authorization_status"] = AuthorizationStatus.NOT_AUTHORIZED
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert any("authorization" in rule for rule in result.expectation.decision_rule_trace)


class TestDeprecatedCase:
    """Tests for deprecated case handling."""

    def test_deprecated_case_returns_error(self):
        """DEPRECATED_CASE error when case is deprecated."""
        case_dict = _make_minimal_case()
        case_dict["governance"] = Governance(
            label_confidence="high",
            authors=["curator_test"],
            reviewers=["reviewer_test"],
            contamination_risk="low",
            deprecation_state="deprecated",
        )
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is False
        assert result.error == CompilationError.DEPRECATED_CASE

    def test_deprecated_case_error_detail_includes_version(self):
        """Error detail includes case version ID for debugging."""
        case_dict = _make_minimal_case()
        case_dict["governance"] = Governance(
            label_confidence="high",
            authors=["curator_test"],
            reviewers=["reviewer_test"],
            contamination_risk="low",
            deprecation_state="deprecated",
        )
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is False
        assert "casev_test_001" in result.error_detail


class TestInvalidCase:
    """Tests for invalid case handling."""

    def test_compiler_rejects_unsupported_version(self):
        """UNSUPPORTED_VERSION error when compiler version is unknown."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("invalid.version.999", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is False
        assert result.error == CompilationError.UNSUPPORTED_VERSION
        assert "invalid.version.999" in result.error_detail


class TestCriticalityDetermination:
    """Tests for criticality level determination."""

    def test_critical_severity_is_high(self):
        """CRITICAL severity maps to high criticality."""
        case_dict = _make_minimal_case()
        case_dict["severity"] = Severity.CRITICAL
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert result.expectation.criticality == "high"

    def test_high_severity_is_high(self):
        """HIGH severity maps to high criticality."""
        case_dict = _make_minimal_case()
        case_dict["severity"] = Severity.HIGH
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert result.expectation.criticality == "high"

    def test_medium_severity_is_medium(self):
        """MEDIUM severity maps to medium criticality."""
        case_dict = _make_minimal_case()
        case_dict["severity"] = Severity.MEDIUM
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert result.expectation.criticality == "medium"

    def test_low_severity_is_low(self):
        """LOW severity maps to low criticality."""
        case_dict = _make_minimal_case()
        case_dict["severity"] = Severity.LOW
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert result.expectation.criticality == "low"


class TestAmbiguousRule:
    """Tests for ambiguous rule detection."""

    def test_ambiguous_rule_detection(self):
        """AMBIGUOUS_RULE error when multiple matching rules exist."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        # Register policy with multiple rules matching same severity
        policy_registry.register("pol_test_1.0.0", {
            "rules": [
                {"severity": "low", "description": "rule 1"},
                {"severity": "low", "description": "rule 2"},  # Duplicate severity
            ],
            "min_rubric_version": "1.0.0",
            "rubric_version": "1.0.0",
        })
        rubric_registry.register("rub_test_1.0.0", {
            "rules": [],
            "rubric_version": "1.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is False
        assert result.error == CompilationError.AMBIGUOUS_RULE

    def test_single_rule_allowed(self):
        """Single rule for severity compiles successfully."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        policy_registry.register("pol_test_1.0.0", {
            "rules": [
                {"severity": "low", "description": "the rule"},
            ],
            "rubric_version": "1.0.0",
        })
        rubric_registry.register("rub_test_1.0.0", {
            "rules": [],
            "rubric_version": "1.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is True
        assert result.expectation is not None

    def test_no_rules_in_policy(self):
        """Policy with no rules compiles successfully (no ambiguity)."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        # Policy with no rules list
        policy_registry.register("pol_test_1.0.0", {
            "rubric_version": "1.0.0",
        })
        rubric_registry.register("rub_test_1.0.0", {
            "rules": [],
            "rubric_version": "1.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is True


class TestVersionCompatibility:
    """Tests for version compatibility checking."""

    def test_unsupported_compiler_version(self):
        """UNSUPPORTED_VERSION error for unknown compiler version."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})

        compiler = ExpectationCompiler("99.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is False
        assert result.error == CompilationError.UNSUPPORTED_VERSION

    def test_policy_rubric_version_mismatch(self):
        """VERSION_MISMATCH error when versions are incompatible."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        # Register policy that requires min_rubric_version 2.0.0
        policy_registry.register("pol_test_1.0.0", {
            "min_rubric_version": "2.0.0",
        })
        # Register rubric version 1.0.0 (incompatible)
        rubric_registry.register("rub_test_1.0.0", {
            "rubric_version": "1.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is False
        assert result.error == CompilationError.VERSION_MISMATCH

    def test_policy_rubric_version_compatible(self):
        """Compatible policy/rubric versions compile successfully."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        # Register compatible versions (rubric 2.0.0 >= min_rubric_version 1.0.0)
        policy_registry.register("pol_test_1.0.0", {
            "min_rubric_version": "1.0.0",
        })
        rubric_registry.register("rub_test_1.0.0", {
            "rubric_version": "2.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is True

    def test_policy_rubric_max_version_exceeded(self):
        """VERSION_MISMATCH when rubric exceeds max_rubric_version."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)

        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()

        # Register policy that max_rubric_version 1.5.0
        policy_registry.register("pol_test_1.0.0", {
            "max_rubric_version": "1.5.0",
        })
        # Register rubric version 2.0.0 (exceeds max)
        rubric_registry.register("rub_test_1.0.0", {
            "rubric_version": "2.0.0",
        })

        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)

        assert result.success is False
        assert result.error == CompilationError.VERSION_MISMATCH


class TestBulkCompilation:
    """Tests for bulk compilation performance and determinism."""

    def test_bulk_compilation_determinism(self):
        """Bulk compilation produces deterministic results."""
        cases = []
        for i in range(100):
            case_dict = _make_minimal_case({
                "case_version_id": f"casev_test_{i:03d}",
            })
            cases.append(_build_case(case_dict))
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"supported_severities": ["low"]})
        rubric_registry.register("rub_test_1.0.0", {"rules": []})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        
        # Compile all cases twice and verify determinism
        results1 = [compiler.compile(case) for case in cases]
        results2 = [compiler.compile(case) for case in cases]
        
        for r1, r2 in zip(results1, results2):
            assert r1.success == r2.success
            if r1.success:
                assert r1.expectation.expectation_id == r2.expectation.expectation_id
                assert r1.expectation.source_case_hash == r2.expectation.source_case_hash


class TestObservationLeakagePrevention:
    """Tests ensuring compiler rejects observation-derived inputs.
    
    Security requirement: The compiler must not accept target responses,
    grades, reviewer outcomes, or provider metadata as inputs.
    """

    def test_compiler_accepts_only_case_inputs(self):
        """Compiler compile() only accepts TestCase, not responses or grades."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        compiler = ExpectationCompiler("1.0.0")
        
        # Verify compile only takes TestCase
        import inspect
        sig = inspect.signature(compiler.compile)
        params = list(sig.parameters.keys())
        assert params == ["case"], f"compile should only take case, got {params}"

    def test_no_response_in_compilation_inputs(self):
        """Verification that response fields are never part of expectation."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"min_rubric_version": "1.0.0", "rubric_version": "1.0.0"})
        rubric_registry.register("rub_test_1.0.0", {"rubric_version": "1.0.0"})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        # ExpectationRecord should not have response-related fields
        assert not hasattr(result.expectation, "response_text")
        assert not hasattr(result.expectation, "provider_metadata")
        assert not hasattr(result.expectation, "grade")


class TestHighHarmCategories:
    """Tests for high-harm category rule inclusion."""

    def test_critical_harm_category_adds_high_harm_rule(self):
        """Critical harm category adds guardrail rule to trace."""
        case_dict = _make_minimal_case()
        case_dict["category"] = "critical_harm"
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert any("high_harm_guardrail" in rule for rule in result.expectation.decision_rule_trace)

    def test_malware_category_adds_high_harm_rule(self):
        """Malware category adds guardrail rule to trace."""
        case_dict = _make_minimal_case()
        case_dict["category"] = "malware"
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert any("high_harm_guardrail" in rule for rule in result.expectation.decision_rule_trace)

    def test_ransomware_category_adds_high_harm_rule(self):
        """Ransomware category adds guardrail rule to trace."""
        case_dict = _make_minimal_case()
        case_dict["category"] = "ransomware"
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert any("high_harm_guardrail" in rule for rule in result.expectation.decision_rule_trace)

    def test_regular_category_no_high_harm_rule(self):
        """Regular categories do not add high harm guardrail."""
        case_dict = _make_minimal_case()
        case_dict["category"] = "general_knowledge"
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {})
        rubric_registry.register("rub_test_1.0.0", {})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        assert result.success is True
        assert not any("high_harm_guardrail" in rule for rule in result.expectation.decision_rule_trace)


class TestCompilationResultSerialization:
    """Tests for CompilationResult serialization."""

    def test_successful_result_to_dict(self):
        """Successful result serializes expectation and version."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        policy_registry = PolicyRegistry()
        rubric_registry = RubricRegistry()
        policy_registry.register("pol_test_1.0.0", {"min_rubric_version": "1.0.0", "rubric_version": "1.0.0"})
        rubric_registry.register("rub_test_1.0.0", {"rubric_version": "1.0.0"})
        
        compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
        result = compiler.compile(case)
        
        serialized = result.to_dict()
        assert serialized["success"] is True
        assert serialized["compiler_version"] == "1.0.0"
        assert "expectation" in serialized
        assert result.error is None

    def test_failed_result_to_dict(self):
        """Failed result serializes error without expectation."""
        case_dict = _make_minimal_case()
        case = _build_case(case_dict)
        
        compiler = ExpectationCompiler("1.0.0")
        
        result = compiler.compile(case)
        
        serialized = result.to_dict()
        assert serialized["success"] is False
        assert serialized["error"] == "missing_policy"
        assert result.expectation is None