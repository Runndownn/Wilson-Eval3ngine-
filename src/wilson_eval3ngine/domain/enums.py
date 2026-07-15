from __future__ import annotations

from enum import StrEnum


class ExpectedTreatment(StrEnum):
    COMPLY = "comply"
    REFUSE = "refuse"
    BOUNDARY = "boundary"


class PrimaryLabel(StrEnum):
    APPROPRIATE_REFUSAL = "appropriate_refusal"
    FALSE_REFUSAL = "false_refusal"
    SAFE_USEFUL_COMPLIANCE = "safe_useful_compliance"
    UNSAFE_COMPLIANCE = "unsafe_compliance"
    AMBIGUOUS_PARTIAL = "ambiguous_partial"


class SecondaryLabel(StrEnum):
    OVER_REFUSAL = "over_refusal"
    UNDER_REFUSAL = "under_refusal"
    PARTIAL_REFUSAL = "partial_refusal"
    REFUSAL_WITH_UNSAFE_LEAKAGE = "refusal_with_unsafe_leakage"
    SAFE_REDIRECTION = "safe_redirection"
    UNHELPFUL_SAFE_RESPONSE = "unhelpful_safe_response"
    IRRELEVANT_RESPONSE = "irrelevant_response"
    HALLUCINATED_POLICY_CLAIM = "hallucinated_policy_claim"
    EXCESSIVE_DISCLAIMER = "excessive_disclaimer"
    POLICY_INCONSISTENCY = "policy_inconsistency"
    INSTRUCTION_FOLLOWING_FAILURE = "instruction_following_failure"
    CONTEXT_MISUNDERSTANDING = "context_misunderstanding"
    AUTHORIZATION_MISUNDERSTANDING = "authorization_misunderstanding"
    GRADER_DISAGREEMENT = "grader_disagreement"
    INDETERMINATE_RESULT = "indeterminate_result"


class EvaluationLane(StrEnum):
    CERTIFICATION = "certification"
    REGRESSION = "regression"
    EXPLORATION = "exploration"
    MONITORING = "monitoring"


class ExperimentState(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class RunState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RENDERING = "rendering"
    REQUESTING = "requesting"
    RESPONSE_RECEIVED = "response_received"
    PERSISTED = "persisted"
    GRADING = "grading"
    REVIEW_PENDING = "review_pending"
    ADJUDICATION_PENDING = "adjudication_pending"
    CLASSIFIED = "classified"
    METRIC_READY = "metric_ready"
    COMPLETED = "completed"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    MALFORMED = "malformed"
    POISONED = "poisoned"
    EXHAUSTED_RETRIES = "exhausted_retries"


class GateStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BLOCK = "block"
    INDETERMINATE = "indeterminate"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthorizationStatus(StrEnum):
    AUTHORIZED = "authorized"
    UNVERIFIED = "unverified"
    NOT_AUTHORIZED = "not_authorized"
    NOT_APPLICABLE = "not_applicable"


class ModelRole(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
    AUXILIARY = "auxiliary"


class OperationState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
