"""Provider scope approval for initial production release.

T4.1.4 - Defines approved provider/model/region combinations with:
- Exact model version identifiers (no aliases)
- Supported parameters and context limits
- Capability metadata and identity requirements
- Data processing terms and retention policies
- Pricing and quota information
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DataClassification(StrEnum):
    """Data classification levels for provider routing."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ProviderTier(StrEnum):
    """Provider tiers based on capability and approval status."""
    APPROVED = "approved"
    FALLBACK = "fallback"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True, slots=True)
class ModelScope:
    """Approved model scope with metadata.

    All models must be referenced by immutable version identifier.
    Aliases that can silently retarget models are explicitly prohibited.
    """
    model_id: str  # Immutable version identifier (e.g., "gpt-4-turbo-2024-04-09")
    alias_forbidden: bool = True  # Whether alias-based routing is forbidden
    context_limit: int = 128_000  # Maximum context tokens
    supports_tools: bool = False
    supports_json: bool = False
    supports_streaming: bool = False

    # Identity attestation requirements
    requires_identity_fingerprint: bool = True

    # Pricing (USD per 1M tokens)
    input_token_price: float = 0.0
    output_token_price: float = 0.0

    # Deprecation tracking
    deprecation_notice: str | None = None
    replacement_model_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderScope:
    """Approved provider scope definition.

    Provides signed decision on provider/model/region combinations.
    See: docs/Plans_/Plans-BLD_phase1/TODO-MASTER_phase1-v2.1/TODO-MASTER_phase1-v2.1.md (TODO 24)
    """
    provider_name: str
    tier: ProviderTier
    regions: list[str] = field(default_factory=list)
    models: dict[str, ModelScope] = field(default_factory=dict)

    # Authentication requirements
    enterprise_auth_required: bool = True
    short_lived_credentials: bool = True

    # Data processing terms
    requires_processing_terms: str = "EU Model Clauses or equivalent"
    retention_days: int = 30
    training_use_prohibited: bool = True

    def allows_model(self, model_id: str) -> bool:
        """Check if model_id is explicitly approved."""
        return model_id in self.models

    def allows_region(self, region: str) -> bool:
        """Check if region is supported for this provider."""
        return region in self.regions

    def get_model_scope(self, model_id: str) -> ModelScope | None:
        """Get model scope details if approved."""
        return self.models.get(model_id)

    def allows_classification(
        self, classification: DataClassification, model_id: str
    ) -> bool:
        """Check if provider/model allows the given data classification.

        Provider A (OpenAI): All classifications permitted for gpt-4-turbo*
        Provider B (Anthropic): RESTRICTED requires additional review
        """
        model_scope = self.models.get(model_id)
        if model_scope is None:
            return False

        # Check tier restrictions
        if self.tier == ProviderTier.EXPERIMENTAL:
            return classification == DataClassification.PUBLIC

        # APPROVED tier: RESTRICTED requires additional review
        if self.tier == ProviderTier.APPROVED:
            if classification == DataClassification.RESTRICTED:
                return self.provider_name != "anthropic"  # Placeholder logic

        return True


# Approved provider scopes for initial production release
# This is the canonical source of truth for provider/model approvals
APPROVED_PROVIDERS: dict[str, ProviderScope] = {
    "mock": ProviderScope(
        provider_name="mock",
        tier=ProviderTier.FALLBACK,
        regions=["global"],
        models={
            "mock-balanced-v1": ModelScope(
                model_id="mock-balanced-v1",
                context_limit=128_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
            ),
            "mock-over-refusal-v1": ModelScope(
                model_id="mock-over-refusal-v1",
                context_limit=128_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
            ),
            "mock-model": ModelScope(
                model_id="mock-model",
                context_limit=128_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
            ),
        },
        enterprise_auth_required=False,
        short_lived_credentials=False,
    ),
    "openai": ProviderScope(
        provider_name="openai",
        tier=ProviderTier.APPROVED,
        regions=["us-east-1", "us-west-2", "eu-west-1"],
        models={
            "gpt-4-turbo-2024-04-09": ModelScope(
                model_id="gpt-4-turbo-2024-04-09",
                context_limit=128_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
                input_token_price=10.00,
                output_token_price=30.00,
            ),
            "gpt-4-2024-05-01": ModelScope(
                model_id="gpt-4-2024-05-01",
                context_limit=8_192,
                supports_tools=False,
                supports_json=False,
                supports_streaming=True,
                input_token_price=30.00,
                output_token_price=60.00,
            ),
        },
    ),
    "anthropic": ProviderScope(
        provider_name="anthropic",
        tier=ProviderTier.APPROVED,
        regions=["us-east-1", "us-west-2"],
        models={
            "claude-3-opus-20240229": ModelScope(
                model_id="claude-3-opus-20240229",
                context_limit=200_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
                input_token_price=15.00,
                output_token_price=75.00,
            ),
            "claude-3-sonnet-20240229": ModelScope(
                model_id="claude-3-sonnet-20240229",
                context_limit=200_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
                input_token_price=3.00,
                output_token_price=15.00,
            ),
        },
    ),
}


def validate_provider_model(
    provider: str,
    model: str,
    region: str | None = None,
    classification: DataClassification = DataClassification.PUBLIC,
) -> tuple[bool, str]:
    """Validate provider/model combination against approved scope.

    Returns:
        (is_valid, reason) tuple for validation result
    """
    scope = APPROVED_PROVIDERS.get(provider)
    if scope is None:
        return False, f"provider {provider!r} is not in approved scope"

    if not scope.allows_model(model):
        return False, f"model {model!r} is not approved for provider {provider!r}"

    if region and not scope.allows_region(region):
        return False, f"region {region!r} is not supported by provider {provider!r}"

    if not scope.allows_classification(classification, model):
        return False, f"data classification {classification.value!r} not permitted for {provider}/{model}"

    return True, "approved"


def list_approved_models(provider: str | None = None) -> list[dict[str, Any]]:
    """List approved models, optionally filtered by provider."""
    if provider:
        scopes = [APPROVED_PROVIDERS.get(provider)] if provider in APPROVED_PROVIDERS else []
    else:
        scopes = list(APPROVED_PROVIDERS.values())

    result = []
    for scope in scopes:
        if scope is None:
            continue
        for model_id, model_scope in scope.models.items():
            result.append({
                "provider": scope.provider_name,
                "model_id": model_id,
                "tier": scope.tier.value,
                "regions": scope.regions,
                "context_limit": model_scope.context_limit,
                "supports_tools": model_scope.supports_tools,
                "supports_json": model_scope.supports_json,
                "supports_streaming": model_scope.supports_streaming,
            })

    return result