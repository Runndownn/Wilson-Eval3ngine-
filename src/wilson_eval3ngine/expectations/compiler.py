from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from ..domain.contracts import ExpectationRecord, TestCase
from ..domain.enums import AuthorizationStatus, Severity
from ..util import canonical_json, sha256_hex, utc_now


class CompilationError(Enum):
    """Explicit terminal failure states for expectation compilation.
    
    Each error is explicit and terminal - no silent defaults are ever used.
    The compiler never accepts target-model responses, grades, or provider metadata
    as inputs, preserving the expectation-before-observation principle.
    """
    INVALID_CASE = "invalid_case"
    MISSING_POLICY = "missing_policy"
    MISSING_RUBRIC = "missing_rubric"
    AMBIGUOUS_RULE = "ambiguous_rule"  # Multiple matching policy rules for same severity
    UNSUPPORTED_VERSION = "unsupported_version"  # Compiler or schema version mismatch
    DEPRECATED_CASE = "deprecated_case"
    VERSION_MISMATCH = "version_mismatch"  # Policy/rubric version incompatibility


@dataclass
class CompilationResult:
    """Result of expectation compilation with either success or explicit failure."""
    success: bool
    expectation: ExpectationRecord | None = None
    error: CompilationError | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "success": self.success,
            "compiler_version": "1.0.0",
        }
        if self.expectation:
            result["expectation"] = self.expectation.model_dump(mode="json")
        if self.error:
            result["error"] = self.error.value
            result["error_detail"] = self.error_detail
        return result


class PolicyRegistry:
    """Policy registry for rule resolution."""

    def __init__(self) -> None:
        self._policies: dict[str, dict[str, Any]] = {}

    def register(self, policy_version_id: str, policy: dict[str, Any]) -> None:
        self._policies[policy_version_id] = policy

    def get(self, policy_version_id: str) -> dict[str, Any] | None:
        return self._policies.get(policy_version_id)

    def supports_severity(self, policy_version_id: str, severity: Severity) -> bool:
        policy = self._policies.get(policy_version_id, {})
        return severity.value in policy.get("supported_severities", ["low", "medium", "high", "critical"])


class RubricRegistry:
    """Rubric registry for grading rules."""

    def __init__(self) -> None:
        self._rubrics: dict[str, dict[str, Any]] = {}

    def register(self, rubric_version_id: str, rubric: dict[str, Any]) -> None:
        self._rubrics[rubric_version_id] = rubric

    def get(self, rubric_version_id: str) -> dict[str, Any] | None:
        return self._rubrics.get(rubric_version_id)


class ExpectationCompiler:
    """Compiles policy/rubric inputs before model execution.

    The compiler is deliberately deterministic. It does not call a model and
    therefore cannot silently reinterpret policy during response grading.
    
    Key security and reliability guarantees:
    - No target-model responses, grades, reviewer outcomes, or provider metadata are accepted as inputs
    - Identical canonical inputs produce byte-identical expectation records and hashes
    - Any validation failure returns an explicit error; no silent defaults
    - Compiler version is recorded; incompatible versions are rejected
    - Policy/rubric version mismatches are detected and reported
    """

    # Supported schema versions for test cases
    SUPPORTED_SCHEMA_VERSIONS: set[str] = {"we3.test_case.v1"}
    SUPPORTED_COMPILER_VERSIONS: set[str] = {"1.0.0"}

    def __init__(
        self,
        rule_version: str,
        policy_registry: PolicyRegistry | None = None,
        rubric_registry: RubricRegistry | None = None,
    ) -> None:
        self.rule_version = rule_version
        self.policy_registry = policy_registry or PolicyRegistry()
        self.rubric_registry = rubric_registry or RubricRegistry()
        
        if rule_version not in self.SUPPORTED_COMPILER_VERSIONS:
            self._compiler_version_valid = False
            self._compiler_version_error = f"unsupported compiler version: {rule_version}"
        else:
            self._compiler_version_valid = True
            self._compiler_version_error = None

    def compile(self, case: TestCase) -> CompilationResult:
        """Compile expectation from case with explicit validation.

        Compilation is deterministic: identical inputs produce identical outputs.
        Any validation failure returns an explicit error, not a silent default.
        """
        # Validate compiler version first
        if not self._compiler_version_valid:
            return CompilationResult(
                success=False,
                error=CompilationError.UNSUPPORTED_VERSION,
                error_detail=self._compiler_version_error,
            )

        # Validate case structure
        error = self._validate_case(case)
        if error:
            return error

        # Validate policy exists
        policy = self.policy_registry.get(case.policy.policy_version_id)
        if policy is None:
            return CompilationResult(
                success=False,
                error=CompilationError.MISSING_POLICY,
                error_detail=f"policy {case.policy.policy_version_id} not found in registry",
            )

        # Validate rubric exists
        rubric = self.rubric_registry.get(case.rubric.rubric_version_id)
        if rubric is None:
            return CompilationResult(
                success=False,
                error=CompilationError.MISSING_RUBRIC,
                error_detail=f"rubric {case.rubric.rubric_version_id} not found in registry",
            )

        # Check for ambiguous rules (multiple matching policy rules)
        if self._has_ambiguous_rules(case, policy):
            return CompilationResult(
                success=False,
                error=CompilationError.AMBIGUOUS_RULE,
                error_detail=f"multiple matching rules for severity {case.severity} in policy {case.policy.policy_version_id}",
            )

        # Check policy/rubric version compatibility
        if not self._versions_compatible(policy, rubric):
            return CompilationResult(
                success=False,
                error=CompilationError.VERSION_MISMATCH,
                error_detail=f"policy {case.policy.policy_version_id} incompatible with rubric {case.rubric.rubric_version_id}",
            )

        # Resolve decision rule trace
        rule_trace = self._resolve_rule_trace(case, policy, rubric)

        expectation = ExpectationRecord(
            expectation_id=sha256_hex(case.content_hash()).replace("'", "")[:32],
            case_version_id=case.case_version_id,
            expected_treatment=case.expected_treatment,
            required_concepts=list(case.required_concepts),
            prohibited_behavior=list(case.prohibited_behavior),
            minimum_usefulness=case.minimum_usefulness,
            materiality_floor=case.materiality_floor,
            policy_version_id=case.policy.policy_version_id,
            rubric_version_id=case.rubric.rubric_version_id,
            rule_version=self.rule_version,
            source_case_hash=case.content_hash(),
            criticality=self._determine_criticality(case),
            decision_rule_trace=rule_trace,
        )

        return CompilationResult(success=True, expectation=expectation)

    def _validate_case(self, case: TestCase) -> CompilationResult | None:
        """Validate case for compilation. Return CompilationResult on error, None on success."""
        # Check deprecated cases
        if case.governance.deprecation_state == "deprecated":
            return CompilationResult(
                success=False,
                error=CompilationError.DEPRECATED_CASE,
                error_detail=f"case {case.case_version_id} is deprecated",
            )

        # Validate severity
        try:
            Severity(case.severity)
        except ValueError:
            return CompilationResult(
                success=False,
                error=CompilationError.INVALID_CASE,
                error_detail=f"invalid severity: {case.severity}",
            )

        return None

    def _has_ambiguous_rules(self, case: TestCase, policy: dict[str, Any]) -> bool:
        """Check if multiple policy rules match the case severity.
        
        This detects ambiguous rule situations where the policy contains
        multiple rules that could apply to the same case.
        """
        # Check if policy has multiple rules with same severity mapping
        rules = policy.get("rules", [])
        if not rules:
            return False
        
        matching_rules = [
            rule for rule in rules
            if rule.get("severity") == case.severity
        ]
        return len(matching_rules) > 1

    def _versions_compatible(self, policy: dict[str, Any], rubric: dict[str, Any]) -> bool:
        """Check if policy and rubric versions are compatible.
        
        Policies and rubrics may declare version compatibility.
        If not declared, default to compatible.
        """
        policy_min_version = policy.get("min_rubric_version")
        policy_max_version = policy.get("max_rubric_version")
        rubric_version = rubric.get("rubric_version")
        
        if policy_min_version and rubric_version and rubric_version < policy_min_version:
            return False
        if policy_max_version and rubric_version and rubric_version > policy_max_version:
            return False
        
        return True

    def _resolve_rule_trace(
        self,
        case: TestCase,
        policy: dict[str, Any],
        rubric: dict[str, Any],
    ) -> list[str]:
        """Resolve decision rules for the case.

        Returns an ordered trace of rules applied during compilation.
        """
        trace = [
            f"case_severity:{case.severity}",
            f"policy:{case.policy.policy_version_id}",
            f"rubric:{case.rubric.rubric_version_id}",
            f"treatment:{case.expected_treatment}",
        ]

        # Add authorization-based rules
        if case.authorization_status == AuthorizationStatus.NOT_AUTHORIZED:
            trace.append("rule:authorization_confidential")
        elif case.authorization_status == AuthorizationStatus.AUTHORIZED:
            trace.append("rule:authorized_compliance")

        # Add category-based rules
        if case.category in ("critical_harm", "malware", "ransomware"):
            trace.append("rule:high_harm_guardrail")

        return trace

    def _determine_criticality(self, case: TestCase) -> str:
        """Determine criticality level for the case."""
        if case.severity in (Severity.CRITICAL.value, Severity.HIGH.value):
            return "high"
        elif case.severity == Severity.MEDIUM.value:
            return "medium"
        return "low"
