"""
Wilson Eval3ngine Tranche B Supply Chain Module.

Curates high-severity hostile and malformed benchmark cases with specialist review,
exposure tier controls, and deterministic simulator fixtures.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import Any


class TrancheBCategory(Enum):
    """Categories for Tranche B hostile/high-severity benchmark cases."""
    CRITICAL_HARM = "critical_harm"
    AUTHORIZATION_COUNTERFACTUAL = "authorization_counterfactual"
    PROMPT_INJECTION = "prompt_injection"
    TOOL_SIMULATION = "tool_simulation"
    MALFORMED_INPUT = "malformed_input"
    HOSTILE_ATTACHMENT = "hostile_attachment"
    RARE_CATEGORY = "rare_category"


class ExposureTier(Enum):
    """Reviewer exposure tier for safety control - ordered by restriction level."""
    TIER_1_STANDARD = 1  # Standard reviewers
    TIER_2_SPECIALIST = 2  # Security specialists only
    TIER_3_CRITICAL = 3   # Highly restricted access


class AttachmentClassification(Enum):
    """Classification for hostile attachments."""
    QUARANTINED = "quarantined"
    INERT_RENDERED = "inert_rendered"
    SAFE_DERIVATIVE = "safe_derivative"
    SIMULATED = "simulated"


@dataclass
class SpecialistReview:
    """Record of a specialist review for high-severity cases."""
    reviewer_id: str
    reviewer_role: str
    reviewer_tier: ExposureTier
    reviewed_at: datetime
    decision: str
    confidence: float
    notes: str | None = None
    exposure_acknowledged: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role,
            "reviewer_tier": self.reviewer_tier.name.lower(),
            "reviewed_at": self.reviewed_at.isoformat(),
            "decision": self.decision,
            "confidence": self.confidence,
            "notes": self.notes,
            "exposure_acknowledged": self.exposure_acknowledged,
        }


@dataclass
class ToolSimulation:
    """Deterministic simulator fixture for tool-use hazard cases."""
    tool_name: str
    simulator_version: str
    fixture_hash: str
    expected_actions: list[str]
    prohibited_actions: list[str]
    safe_args_only: bool = True
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "simulator_version": self.simulator_version,
            "fixture_hash": self.fixture_hash,
            "expected_actions": self.expected_actions,
            "prohibited_actions": self.prohibited_actions,
            "safe_args_only": self.safe_args_only,
            "seed": self.seed,
        }

    @classmethod
    def create(cls, tool_name: str, prompt: str, expected_actions: list[str],
               prohibited_actions: list[str], simulator_version: str = "1.0.0",
               seed: int = 42) -> "ToolSimulation":
        """Create a tool simulation with deterministic hash."""
        fixture_hash = sha256(f"{tool_name}:{prompt}".encode()).hexdigest()
        return cls(
            tool_name=tool_name,
            simulator_version=simulator_version,
            fixture_hash=fixture_hash,
            expected_actions=expected_actions,
            prohibited_actions=prohibited_actions,
            seed=seed,
        )


@dataclass
class HostileAttachment:
    """Metadata for quarantined hostile attachments."""
    hash_sha256: str
    media_type: str
    classification: AttachmentClassification
    scanner_verdict: str
    retention_required: bool = True
    simulator_fixture: ToolSimulation | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "hash_sha256": self.hash_sha256,
            "media_type": self.media_type,
            "classification": self.classification.value,
            "scanner_verdict": self.scanner_verdict,
            "retention_required": self.retention_required,
        }
        if self.simulator_fixture:
            result["simulator_fixture"] = self.simulator_fixture.to_dict()
        return result


@dataclass
class TrancheBCase:
    """A high-severity or hostile benchmark case for Tranche B."""
    case_id: str
    family: str
    category: TrancheBCategory
    severity: str
    language: str
    prompt: str
    expected_outcome: str
    expected_treatment: str
    policy_version: str
    rubric_version: str
    specialist_reviews: list[SpecialistReview] = field(default_factory=list)
    adjudication: dict[str, Any] | None = None
    attachments: list[HostileAttachment] = field(default_factory=list)
    tool_simulations: list[ToolSimulation] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    exposure_tier_required: ExposureTier = ExposureTier.TIER_2_SPECIALIST
    safe_derivative_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for manifest output."""
        return {
            "case_id": self.case_id,
            "family": self.family,
            "category": self.category.value,
            "severity": self.severity,
            "language": self.language,
            "prompt": self.prompt,
            "expected_outcome": self.expected_outcome,
            "expected_treatment": self.expected_treatment,
            "policy_reference": {
                "policy_version": self.policy_version,
                "rubric_version": self.rubric_version,
            },
            "review_status": {
                "status": self._get_review_status(),
                "review_count": len(self.specialist_reviews),
                "required_review_count": 2,
                "exposure_tier_required": self.exposure_tier_required.name.lower(),
            },
            "safety_controls": {
                "quarantined_attachments": len(self.attachments),
                "tool_simulations": len(self.tool_simulations),
                "safe_derivative_available": self.safe_derivative_available,
            },
            "tags": self.tags,
        }

    def _get_review_status(self) -> str:
        """Determine review status for specialist review."""
        if len(self.specialist_reviews) < 2:
            return "pending_specialist_review"

        unique_reviewers = {r.reviewer_id for r in self.specialist_reviews}
        if len(unique_reviewers) < 2:
            return "incomplete_specialist_review"

        decisions = [r.decision for r in self.specialist_reviews]
        if len(set(decisions)) == 1:
            return "specialist_reviewed"
        return "specialist_adjudication_needed"

    def add_specialist_review(
        self,
        reviewer_id: str,
        reviewer_role: str,
        reviewer_tier: ExposureTier,
        decision: str,
        confidence: float = 0.95,
        notes: str | None = None,
    ) -> bool:
        """Add a specialist review decision."""
        if any(r.reviewer_id == reviewer_id for r in self.specialist_reviews):
            return False

        if reviewer_tier.value < self.exposure_tier_required.value:
            return False

        self.specialist_reviews.append(SpecialistReview(
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            reviewer_tier=reviewer_tier,
            reviewed_at=datetime.now(UTC),
            decision=decision,
            confidence=confidence,
            notes=notes,
        ))
        return True

    def is_fully_reviewed(self) -> bool:
        """Check if case has required dual independent specialist reviews."""
        unique_reviewers = {r.reviewer_id for r in self.specialist_reviews}
        if len(unique_reviewers) < 2:
            return False
        decisions = [r.decision for r in self.specialist_reviews]
        return len(set(decisions)) == 1

    def add_tool_simulation(self, simulation: ToolSimulation) -> None:
        """Add a tool simulation fixture."""
        self.tool_simulations.append(simulation)

    def add_quarantined_attachment(self, attachment: HostileAttachment) -> None:
        """Add a quarantined hostile attachment."""
        self.attachments.append(attachment)


class TrancheBCurator:
    """
    Curates Tranche B hostile and high-severity benchmark cases.

    Implements specialist review workflow, simulator fixtures, and
    quarantine controls for safety-critical content testing.
    """

    def __init__(self, tranche_name: str = "tranche_b_hostile_inputs"):
        self.tranche_name = tranche_name
        self.cases: list[TrancheBCase] = []
        self._case_by_id: dict[str, TrancheBCase] = {}

    def create_critical_harm_case(
        self,
        prompt: str,
        language: str = "en",
        expected_treatment: str = "refuse",
        policy_version: str = "2026-07-15",
        rubric_version: str = "critical_harm.v1",
        tags: list[str] | None = None,
    ) -> TrancheBCase:
        """Create a critical-harm test case (requires tier 3 review)."""
        case = TrancheBCase(
            case_id=str(uuid.uuid4()),
            family="critical_harm",
            category=TrancheBCategory.CRITICAL_HARM,
            severity="critical",
            language=language,
            prompt=prompt,
            expected_outcome="appropriate_refusal",
            expected_treatment=expected_treatment,
            policy_version=policy_version,
            rubric_version=rubric_version,
            tags=tags or ["critical", "harm"],
            exposure_tier_required=ExposureTier.TIER_3_CRITICAL,
        )
        self._add_case(case)
        return case

    def create_authorization_counterfactual_case(
        self,
        prompt: str,
        language: str = "en",
        expected_treatment: str = "refuse",
    ) -> TrancheBCase:
        """Create an authorization counterfactual test case."""
        case = TrancheBCase(
            case_id=str(uuid.uuid4()),
            family="authorization_counterfactual",
            category=TrancheBCategory.AUTHORIZATION_COUNTERFACTUAL,
            severity="high",
            language=language,
            prompt=prompt,
            expected_outcome="appropriate_refusal",
            expected_treatment=expected_treatment,
            policy_version="2026-07-15",
            rubric_version="auth_counterfactual.v1",
            tags=["counterfactual", "authorization"],
            exposure_tier_required=ExposureTier.TIER_2_SPECIALIST,
        )
        self._add_case(case)
        return case

    def create_prompt_injection_case(
        self,
        prompt: str,
        language: str = "en",
        expected_treatment: str = "refuse",
    ) -> TrancheBCase:
        """Create a prompt injection test case."""
        case = TrancheBCase(
            case_id=str(uuid.uuid4()),
            family="prompt_injection",
            category=TrancheBCategory.PROMPT_INJECTION,
            severity="high",
            language=language,
            prompt=prompt,
            expected_outcome="appropriate_refusal",
            expected_treatment=expected_treatment,
            policy_version="2026-07-15",
            rubric_version="prompt_injection.v1",
            tags=["injection", "prompt"],
            exposure_tier_required=ExposureTier.TIER_2_SPECIALIST,
        )
        self._add_case(case)
        return case

    def create_tool_simulation_case(
        self,
        tool_name: str,
        prompt: str,
        expected_actions: list[str],
        prohibited_actions: list[str],
        simulator_version: str = "1.0.0",
        seed: int = 42,
    ) -> TrancheBCase:
        """Create a tool simulation test case."""
        case = TrancheBCase(
            case_id=str(uuid.uuid4()),
            family=f"tool_sim_{tool_name}",
            category=TrancheBCategory.TOOL_SIMULATION,
            severity="high",
            language="en",
            prompt=prompt,
            expected_outcome="simulation_verified",
            expected_treatment="comply",
            policy_version="2026-07-15",
            rubric_version="tool_simulation.v1",
            tags=["tool", "simulation", tool_name],
            exposure_tier_required=ExposureTier.TIER_2_SPECIALIST,
        )

        simulation = ToolSimulation.create(
            tool_name=tool_name,
            prompt=prompt,
            expected_actions=expected_actions,
            prohibited_actions=prohibited_actions,
            simulator_version=simulator_version,
            seed=seed,
        )
        case.add_tool_simulation(simulation)
        self._add_case(case)
        return case

    def create_malformed_input_case(
        self,
        prompt: str,
        language: str = "en",
        expected_outcome: str = "safe_error",
        expected_treatment: str = "comply",
    ) -> TrancheBCase:
        """Create a malformed input test case."""
        case = TrancheBCase(
            case_id=str(uuid.uuid4()),
            family="malformed_input",
            category=TrancheBCategory.MALFORMED_INPUT,
            severity="medium",
            language=language,
            prompt=prompt,
            expected_outcome=expected_outcome,
            expected_treatment=expected_treatment,
            policy_version="2026-07-15",
            rubric_version="malformed_input.v1",
            tags=["malformed", "validation"],
            exposure_tier_required=ExposureTier.TIER_1_STANDARD,
        )
        self._add_case(case)
        return case

    def _add_case(self, case: TrancheBCase) -> None:
        """Register case in curator."""
        self.cases.append(case)
        self._case_by_id[case.case_id] = case

    def get_fully_reviewed_cases(self) -> list[TrancheBCase]:
        """Get cases that have completed dual specialist review."""
        return [c for c in self.cases if c.is_fully_reviewed()]

    def get_pending_review_cases(self) -> list[TrancheBCase]:
        """Get cases pending specialist review."""
        return [c for c in self.cases if not c.is_fully_reviewed()]

    def get_critical_cases(self) -> list[TrancheBCase]:
        """Get critical-severity cases requiring highest review standards."""
        return [c for c in self.cases if c.severity == "critical"]

    def generate_tranche_manifest(self, version: str = "1.0.0") -> dict[str, Any]:
        """Generate manifest for the complete tranche."""
        fully_reviewed = self.get_fully_reviewed_cases()
        critical_cases = self.get_critical_cases()

        return {
            "schema_version": "benchmark_tranche_manifest.v1",
            "tranche_id": f"tranche_b_{version}",
            "tranche_name": self.tranche_name,
            "version": version,
            "policy_version": "2026-07-15",
            "rubric_version": "hostile-inputs.v1",
            "case_count": len(self.cases),
            "fully_reviewed_count": len(fully_reviewed),
            "critical_severe_count": len(critical_cases),
            "cases": [c.to_dict() for c in self.cases],
            "security_controls": {
                "quarantine_required": True,
                "simulator_fixtures_only": True,
                "no_live_targets": True,
                "no_actionable_secrets": True,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def generate_defensive_translation(self, case: TrancheBCase) -> dict[str, Any]:
        """Generate defensive translation for a hostile case."""
        detection_ideas = [
            "validate_input_structure",
            "detect_malicious_artifacts",
        ]
        hardening_actions = [
            "sanitize_user_input",
            "apply_prompt_guardrails",
            "quarantine_suspicious_attachments",
        ]

        if case.category == TrancheBCategory.PROMPT_INJECTION:
            detection_ideas.extend(["detect_injection_separators", "check_role_confusion"])
            hardening_actions.extend(["apply_separation_guards", "filter_special_characters"])

        if case.category == TrancheBCategory.TOOL_SIMULATION:
            detection_ideas.extend(["validate_tool_permissions", "check_tool_dangerous_ops"])
            hardening_actions.extend(["enforce_tool_sandbox", "audit_tool_calls"])

        if case.category == TrancheBCategory.CRITICAL_HARM:
            detection_ideas.extend(["classify_harm_severity", "detect_undue_detail"])
            hardening_actions.extend(["apply_harm_guardrails"])

        return {
            "technique_observed": case.family,
            "attack_precondition": "malicious input",
            "vulnerable_configuration": "unvalidated input processing",
            "logs_that_would_show_it": ["prompt_handling", "refusal_decision"],
            "detection_ideas": detection_ideas,
            "hardening_actions": hardening_actions,
            "blue_team_summary": f"Validate {case.expected_treatment} for {case.category.value}",
            "review_safety": {
                "exposure_tier": case.exposure_tier_required.name.lower(),
                "simulated_content_only": True,
            },
        }