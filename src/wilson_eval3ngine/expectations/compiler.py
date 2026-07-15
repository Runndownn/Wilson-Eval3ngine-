from __future__ import annotations

from ..domain.contracts import ExpectationRecord, TestCase
from ..util import new_id


class ExpectationCompiler:
    """Compiles policy/rubric inputs before model execution.

    The compiler is deliberately deterministic. It does not call a model and
    therefore cannot silently reinterpret policy during response grading.
    """

    def __init__(self, rule_version: str) -> None:
        self.rule_version = rule_version

    def compile(self, case: TestCase) -> ExpectationRecord:
        return ExpectationRecord(
            expectation_id=new_id("expct"),
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
        )
