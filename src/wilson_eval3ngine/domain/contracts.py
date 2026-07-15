from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    AuthorizationStatus,
    EvaluationLane,
    ExpectedTreatment,
    GateStatus,
    ModelRole,
    OperationState,
    PrimaryLabel,
    RunState,
    SecondaryLabel,
    Severity,
)
from ..util import canonical_json, sha256_hex, utc_now


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, validate_assignment=True)

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.model_dump(mode="json", exclude_none=True))

    def content_hash(self) -> str:
        return sha256_hex(self.canonical_bytes())


class ContentBlock(ContractModel):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=100_000)


class ConversationTurn(ContractModel):
    role: Literal["system", "user", "assistant"]
    content: list[ContentBlock] = Field(min_length=1)


class Conversation(ContractModel):
    system: list[ContentBlock] = Field(default_factory=list)
    turns: list[ConversationTurn] = Field(min_length=1)


class PolicyRef(ContractModel):
    policy_version_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=20_000)


class RubricRef(ContractModel):
    rubric_version_id: str = Field(min_length=1)
    grader_instructions_ref: str | None = None


class Governance(ContractModel):
    label_confidence: Literal["high", "medium", "low"]
    authors: list[str] = Field(min_length=1)
    reviewers: list[str] = Field(min_length=1)
    adjudicator: str | None = None
    contamination_risk: Literal["low", "medium", "high"] = "low"
    deprecation_state: Literal["active", "deprecated", "retired"] = "active"


class Lineage(ContractModel):
    source_ids: list[str] = Field(default_factory=list)
    content_sha256: str | None = None


class TestCase(ContractModel):
    schema_version: Literal["we3.test_case.v1"] = "we3.test_case.v1"
    case_version_id: str = Field(min_length=1)
    dataset_version_id: str = Field(min_length=1)
    prompt_family_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    split: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2)
    category: str = Field(min_length=1)
    subcategory: str = Field(min_length=1)
    severity: Severity
    authorization_status: AuthorizationStatus
    user_intent: str = Field(min_length=1)
    requested_capability: str = Field(min_length=1)
    conversation: Conversation
    expected_treatment: ExpectedTreatment
    acceptable_alternatives: list[str] = Field(default_factory=list)
    expected_primary_outcomes: list[PrimaryLabel] = Field(default_factory=list)
    prohibited_behavior: list[str] = Field(default_factory=list)
    required_concepts: list[str] = Field(default_factory=list)
    minimum_usefulness: int = Field(default=2, ge=0, le=4)
    materiality_floor: int = Field(default=2, ge=0, le=4)
    policy: PolicyRef
    rubric: RubricRef
    governance: Governance
    lineage: Lineage
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_expected_outcomes(self) -> "TestCase":
        if not self.expected_primary_outcomes:
            if self.expected_treatment == ExpectedTreatment.COMPLY:
                self.expected_primary_outcomes = [PrimaryLabel.SAFE_USEFUL_COMPLIANCE]
            elif self.expected_treatment == ExpectedTreatment.REFUSE:
                self.expected_primary_outcomes = [PrimaryLabel.APPROPRIATE_REFUSAL]
            else:
                self.expected_primary_outcomes = [PrimaryLabel.AMBIGUOUS_PARTIAL]
        return self


class DatasetManifest(ContractModel):
    schema_version: Literal["we3.dataset.v1"] = "we3.dataset.v1"
    dataset_id: str = Field(min_length=1)
    dataset_version_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    split: str = Field(min_length=1)
    cases: list[TestCase] = Field(min_length=1)
    declared_sha256: str | None = None

    @model_validator(mode="after")
    def validate_case_membership(self) -> "DatasetManifest":
        ids: set[str] = set()
        for case in self.cases:
            if case.dataset_version_id != self.dataset_version_id:
                raise ValueError(
                    f"case {case.case_version_id} belongs to "
                    f"{case.dataset_version_id}, expected {self.dataset_version_id}"
                )
            if case.split != self.split:
                raise ValueError(
                    f"case {case.case_version_id} split {case.split!r} "
                    f"does not match dataset split {self.split!r}"
                )
            if case.case_version_id in ids:
                raise ValueError(f"duplicate case_version_id: {case.case_version_id}")
            ids.add(case.case_version_id)
        if self.declared_sha256 and self.declared_sha256 != self.computed_sha256():
            raise ValueError("dataset declared_sha256 does not match canonical content")
        return self

    def computed_sha256(self) -> str:
        payload = self.model_dump(mode="json", exclude={"declared_sha256"}, exclude_none=True)
        return sha256_hex(payload)


class DatasetRef(ContractModel):
    dataset_id: str
    version: str
    split: str
    manifest_sha256: str | Literal["auto"] = "auto"
    local_path: str | None = None


class ModelConfiguration(ContractModel):
    model_config_id: str
    role: ModelRole
    provider: str
    model: str
    profile: str = "balanced"
    parameters: dict[str, Any] = Field(default_factory=dict)

    def configuration_hash(self) -> str:
        return self.content_hash()


class RandomizationConfig(ContractModel):
    case_order: Literal["seeded", "fixed"] = "seeded"
    seed: int = 20260714


class ConcurrencyConfig(ContractModel):
    global_limit: int = Field(default=8, ge=1, le=10_000, alias="global")
    per_provider: int = Field(default=4, ge=1, le=10_000)

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
        populate_by_name=True,
    )


class ExecutionConfig(ContractModel):
    repetitions: int = Field(default=1, ge=1, le=100)
    randomization: RandomizationConfig = Field(default_factory=RandomizationConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    deadline_minutes: int = Field(default=60, ge=1, le=10_080)
    response_cache: Literal["disabled", "enabled"] = "disabled"
    streaming: Literal["assemble_and_store_chunks", "disabled"] = "disabled"


class RetryPolicy(ContractModel):
    max_attempts: int = Field(default=4, ge=1, le=10)
    initial_backoff_seconds: float = Field(default=2.0, ge=0)
    maximum_backoff_seconds: float = Field(default=60.0, ge=0)
    maximum_elapsed_seconds: float = Field(default=300.0, ge=0)
    jitter: Literal["full", "none"] = "full"
    retryable_classes: list[str] = Field(
        default_factory=lambda: [
            "provider_rate_limit",
            "provider_5xx",
            "network_transient",
        ]
    )


class GraderConfig(ContractModel):
    expectation_rule_version: str
    deterministic_suite: str
    semantic_classifier: str | None = None
    judges: list[str] = Field(default_factory=list)
    fusion: str
    review_policy: str


class MetricConfig(ContractModel):
    definitions: list[str] = Field(min_length=1)
    statistical_plan: str


class ReleaseConfig(ContractModel):
    threshold_set: str
    baseline_experiment_id: str | None = None
    require_all_critical_reviews: bool = True
    require_signed_dossier: bool = True
    minimum_prompt_families: int = Field(default=30, ge=1)


class BudgetConfig(ContractModel):
    provider_currency_hard: float = Field(default=100.0, ge=0)
    grading_currency_hard: float = Field(default=50.0, ge=0)
    human_review_tasks_hard: int = Field(default=100, ge=0)
    storage_gib_hard: float = Field(default=10.0, ge=0)


class RetentionConfig(ContractModel):
    policy_id: str
    legal_hold: bool = False


class ExperimentManifest(ContractModel):
    schema_version: Literal["we3.experiment.v1"] = "we3.experiment.v1"
    name: str = Field(min_length=1)
    project: str = Field(min_length=1)
    lane: EvaluationLane
    purpose: str = Field(min_length=1)
    dataset: DatasetRef
    models: list[ModelConfiguration] = Field(min_length=1)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    graders: GraderConfig
    metrics: MetricConfig
    release: ReleaseConfig
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    retention: RetentionConfig
    outputs: list[
        Literal["json", "jsonl", "csv", "parquet", "safe_html", "release_dossier"]
    ] = Field(default_factory=lambda: ["json", "safe_html", "release_dossier"])
    notifications: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_certification_rules(self) -> "ExperimentManifest":
        ids = [model.model_config_id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("model_config_id values must be unique")
        if self.lane == EvaluationLane.CERTIFICATION:
            if self.execution.response_cache != "disabled":
                raise ValueError("certification response caching must be disabled")
            if any(model.role == ModelRole.CANDIDATE for model in self.models) is False:
                raise ValueError("certification requires at least one candidate model")
        return self


class ExpectationRecord(ContractModel):
    schema_version: Literal["we3.expectation.v1"] = "we3.expectation.v1"
    expectation_id: str
    case_version_id: str
    expected_treatment: ExpectedTreatment
    required_concepts: list[str]
    prohibited_behavior: list[str]
    minimum_usefulness: int
    materiality_floor: int
    policy_version_id: str
    rubric_version_id: str
    rule_version: str
    source_case_hash: str
    compiled_at: datetime = Field(default_factory=utc_now)


class ProviderRequest(ContractModel):
    schema_version: Literal["we3.provider_request.v1"] = "we3.provider_request.v1"
    run_id: str
    model_config_id: str
    provider: str
    model: str
    messages: list[ConversationTurn]
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=60.0, gt=0)


class ProviderResponse(ContractModel):
    schema_version: Literal["we3.provider_response.v1"] = "we3.provider_response.v1"
    run_id: str
    attempt_id: str
    protocol_valid: bool = True
    terminal: bool = True
    text: str = ""
    provider_reported_model: str
    finish_reason: str = "stop"
    usage: dict[str, int | float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_class: str | None = None
    retryable: bool = False
    received_at: datetime = Field(default_factory=utc_now)


class DetectorEvidence(ContractModel):
    refusal_detected: bool
    core_request_refused: bool
    unsafe_materiality: int = Field(ge=0, le=4)
    usefulness_score: int = Field(ge=0, le=4)
    required_concepts_found: list[str] = Field(default_factory=list)
    required_concepts_missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Classification(ContractModel):
    schema_version: Literal["we3.classification.v1"] = "we3.classification.v1"
    classification_id: str
    run_id: str
    primary_label: PrimaryLabel
    secondary_labels: list[SecondaryLabel] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    evidence: DetectorEvidence
    grader_version: str
    created_at: datetime = Field(default_factory=utc_now)


class RunResult(ContractModel):
    run_id: str
    logical_key: str
    project_id: str
    experiment_id: str
    case_version_id: str
    prompt_family_id: str
    model_config_id: str
    repetition_index: int
    expected_treatment: ExpectedTreatment
    state: RunState
    request_artifact_hash: str | None = None
    response_artifact_hash: str | None = None
    classification: Classification | None = None
    reliability_error: str | None = None


class Interval(ContractModel):
    lower: float = Field(ge=0, le=1)
    upper: float = Field(ge=0, le=1)
    confidence: float = Field(default=0.95, gt=0, lt=1)


class MetricResult(ContractModel):
    metric_id: str
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None = Field(default=None, ge=0, le=1)
    interval: Interval | None = None
    exclusions: dict[str, int] = Field(default_factory=dict)
    method: str = "proportion"
    direction: Literal["higher", "lower", "descriptive"]
    definition_version: str = "1.0.0"


class MetricSnapshot(ContractModel):
    schema_version: Literal["we3.metric_snapshot.v1"] = "we3.metric_snapshot.v1"
    snapshot_id: str
    experiment_id: str
    model_config_id: str
    run_ids: list[str]
    counts: dict[str, int]
    metrics: list[MetricResult]
    prompt_family_count: int
    created_at: datetime = Field(default_factory=utc_now)
    snapshot_sha256: str | None = None

    def finalize(self) -> "MetricSnapshot":
        payload = self.model_dump(mode="json", exclude={"snapshot_sha256"}, exclude_none=True)
        self.snapshot_sha256 = sha256_hex(payload)
        return self


class ThresholdRule(ContractModel):
    metric_id: str
    comparison: Literal["max_point", "max_upper", "min_point", "min_lower"]
    warning: float | None = Field(default=None, ge=0, le=1)
    block: float | None = Field(default=None, ge=0, le=1)
    minimum_denominator: int = Field(default=1, ge=1)
    critical: bool = False


class ThresholdSet(ContractModel):
    schema_version: Literal["we3.threshold_set.v1"] = "we3.threshold_set.v1"
    threshold_set_id: str
    version: str
    minimum_prompt_families: int = Field(default=30, ge=1)
    rules: list[ThresholdRule] = Field(min_length=1)


class GateCheck(ContractModel):
    metric_id: str
    status: GateStatus
    observed: float | None
    compared_value: float | None
    message: str


class GateDecision(ContractModel):
    schema_version: Literal["we3.gate_decision.v1"] = "we3.gate_decision.v1"
    gate_id: str
    experiment_id: str
    model_config_id: str
    status: GateStatus
    checks: list[GateCheck]
    reasons: list[str]
    threshold_set_id: str
    created_at: datetime = Field(default_factory=utc_now)


class Operation(ContractModel):
    operation_id: str
    project_id: str = Field(min_length=1, max_length=128)
    state: OperationState = OperationState.PENDING
    manifest_path: str
    output_dir: str
    result_path: str | None = None
    error_code: str | None = None
    safe_detail: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
