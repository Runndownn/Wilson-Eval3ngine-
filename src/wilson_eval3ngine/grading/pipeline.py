from __future__ import annotations

from ..domain.contracts import (
    Classification,
    ExpectationRecord,
    ProviderResponse,
    TestCase,
)
from .classifier import DeterministicClassifier
from .deterministic import DeterministicEvidenceExtractor


class GradingPipeline:
    """Foundation grading pipeline.

    This pipeline is intentionally deterministic and pluggable. It is not a
    certification-approved grader and must be calibrated against an adjudicated
    hidden set before production use.
    """

    def __init__(self) -> None:
        self.extractor = DeterministicEvidenceExtractor()
        self.classifier = DeterministicClassifier()

    def grade(
        self,
        *,
        case: TestCase,
        expectation: ExpectationRecord,
        response: ProviderResponse,
    ) -> Classification:
        evidence = self.extractor.analyze(expectation, response)
        return self.classifier.classify(
            case=case,
            expectation=expectation,
            response=response,
            evidence=evidence,
        )
