"""Fail-closed provider/model scope policy.

Production provider approvals are governance data, not permanent source-code
facts. The repository therefore ships only deterministic local mock scope. Real
provider/model/region/data-classification approvals must be registered from an
explicit reviewed policy (optionally via ``WE3_PROVIDER_SCOPE_FILE``) and are
bound to exact model identifiers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ProviderTier(StrEnum):
    APPROVED = "approved"
    FALLBACK = "fallback"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True, slots=True)
class ModelScope:
    """Exact model approval and capability policy."""

    model_id: str
    alias_forbidden: bool = True
    context_limit: int = 128_000
    supports_tools: bool = False
    supports_json: bool = False
    supports_streaming: bool = False
    requires_identity_fingerprint: bool = True
    allowed_classifications: frozenset[DataClassification] = field(
        default_factory=lambda: frozenset({DataClassification.PUBLIC})
    )
    deprecation_notice: str | None = None
    replacement_model_id: str | None = None
    # Cost information is informational evidence, never an approval predicate.
    input_token_price: float | None = None
    output_token_price: float | None = None

    def __post_init__(self) -> None:
        if not self.model_id or self.model_id.strip() != self.model_id:
            raise ValueError("model_id must be a non-empty exact identifier")
        if self.context_limit <= 0:
            raise ValueError("context_limit must be positive")
        if not self.allowed_classifications:
            raise ValueError("model scope must allow at least one data classification")
        normalized = frozenset(DataClassification(item) for item in self.allowed_classifications)
        object.__setattr__(self, "allowed_classifications", normalized)
        for price in (self.input_token_price, self.output_token_price):
            if price is not None and price < 0:
                raise ValueError("token prices cannot be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelScope":
        allowed = value.get("allowed_classifications", [DataClassification.PUBLIC.value])
        if not isinstance(allowed, list):
            raise ValueError("allowed_classifications must be a list")
        return cls(
            model_id=str(value["model_id"]),
            alias_forbidden=bool(value.get("alias_forbidden", True)),
            context_limit=int(value.get("context_limit", 128_000)),
            supports_tools=bool(value.get("supports_tools", False)),
            supports_json=bool(value.get("supports_json", False)),
            supports_streaming=bool(value.get("supports_streaming", False)),
            requires_identity_fingerprint=bool(value.get("requires_identity_fingerprint", True)),
            allowed_classifications=frozenset(DataClassification(str(item)) for item in allowed),
            deprecation_notice=(str(value["deprecation_notice"]) if value.get("deprecation_notice") else None),
            replacement_model_id=(str(value["replacement_model_id"]) if value.get("replacement_model_id") else None),
            input_token_price=(float(value["input_token_price"]) if value.get("input_token_price") is not None else None),
            output_token_price=(float(value["output_token_price"]) if value.get("output_token_price") is not None else None),
        )


@dataclass(frozen=True, slots=True)
class ProviderScope:
    """Versioned exact provider scope supplied by governance policy."""

    provider_name: str
    tier: ProviderTier
    regions: tuple[str, ...] = ()
    models: Mapping[str, ModelScope] = field(default_factory=dict)
    enterprise_auth_required: bool = True
    short_lived_credentials: bool = True
    processing_terms_ref: str | None = None
    retention_days: int | None = None
    training_use_prohibited: bool = True
    policy_version: str = "unversioned"

    def __post_init__(self) -> None:
        if not self.provider_name or self.provider_name.strip() != self.provider_name:
            raise ValueError("provider_name must be a non-empty exact identifier")
        if not self.policy_version or self.policy_version.strip() != self.policy_version:
            raise ValueError("policy_version is required")
        regions = tuple(dict.fromkeys(str(region) for region in self.regions))
        if any(not region for region in regions):
            raise ValueError("regions must be non-empty exact identifiers")
        models = dict(self.models)
        if not models:
            raise ValueError("provider scope must contain at least one model")
        for key, model in models.items():
            if key != model.model_id:
                raise ValueError("model mapping key must equal exact model_id")
        if self.retention_days is not None and self.retention_days < 0:
            raise ValueError("retention_days cannot be negative")
        object.__setattr__(self, "regions", regions)
        object.__setattr__(self, "models", MappingProxyType(models))

    def allows_model(self, model_id: str) -> bool:
        return model_id in self.models

    def allows_region(self, region: str) -> bool:
        return region in self.regions

    def get_model_scope(self, model_id: str) -> ModelScope | None:
        return self.models.get(model_id)

    def allows_classification(self, classification: DataClassification, model_id: str) -> bool:
        model = self.models.get(model_id)
        if model is None:
            return False
        return classification in model.allowed_classifications

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProviderScope":
        raw_models = value.get("models")
        if not isinstance(raw_models, list) or not raw_models:
            raise ValueError("provider policy models must be a non-empty list")
        models = [ModelScope.from_dict(item) for item in raw_models if isinstance(item, Mapping)]
        if len(models) != len(raw_models):
            raise ValueError("every provider policy model must be an object")
        return cls(
            provider_name=str(value["provider_name"]),
            tier=ProviderTier(str(value["tier"])),
            regions=tuple(str(item) for item in value.get("regions", [])),
            models={model.model_id: model for model in models},
            enterprise_auth_required=bool(value.get("enterprise_auth_required", True)),
            short_lived_credentials=bool(value.get("short_lived_credentials", True)),
            processing_terms_ref=(str(value["processing_terms_ref"]) if value.get("processing_terms_ref") else None),
            retention_days=(int(value["retention_days"]) if value.get("retention_days") is not None else None),
            training_use_prohibited=bool(value.get("training_use_prohibited", True)),
            policy_version=str(value.get("policy_version", "")),
        )


_ALL_CLASSIFICATIONS = frozenset(DataClassification)

# The only source-controlled approval is the deterministic local mock. Shipping a
# real vendor here would silently turn dated source metadata into production
# governance authority.
APPROVED_PROVIDERS: dict[str, ProviderScope] = {
    "mock": ProviderScope(
        provider_name="mock",
        tier=ProviderTier.FALLBACK,
        regions=("local", "global"),
        models={
            model_id: ModelScope(
                model_id=model_id,
                context_limit=128_000,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
                requires_identity_fingerprint=False,
                allowed_classifications=_ALL_CLASSIFICATIONS,
            )
            for model_id in ("mock-balanced-v1", "mock-over-refusal-v1", "mock-model")
        },
        enterprise_auth_required=False,
        short_lived_credentials=False,
        processing_terms_ref=None,
        retention_days=None,
        training_use_prohibited=True,
        policy_version="builtin-mock-v1",
    )
}


def register_provider_scope(scope: ProviderScope, *, replace: bool = False) -> None:
    """Register one reviewed scope, rejecting accidental policy mutation."""
    existing = APPROVED_PROVIDERS.get(scope.provider_name)
    if existing is not None and existing != scope and not replace:
        raise ValueError(f"provider scope already registered: {scope.provider_name}")
    APPROVED_PROVIDERS[scope.provider_name] = scope


def load_provider_scope_file(path: Path | str, *, replace: bool = False) -> list[str]:
    """Load an explicit versioned provider policy from JSON.

    Schema::

        {"schema_version":"we3.provider_scope.v1","providers":[...]}

    Unknown top-level schema versions fail closed. Registration is validated as a
    complete batch before global policy is modified.
    """
    policy_path = Path(path)
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "we3.provider_scope.v1":
        raise ValueError("unsupported provider scope schema")
    raw_providers = data.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        raise ValueError("provider scope file must contain providers")
    scopes = [ProviderScope.from_dict(item) for item in raw_providers if isinstance(item, Mapping)]
    if len(scopes) != len(raw_providers):
        raise ValueError("every provider scope entry must be an object")
    names = [scope.provider_name for scope in scopes]
    if len(names) != len(set(names)):
        raise ValueError("provider scope file contains duplicate provider names")
    if not replace:
        conflicts = [name for name in names if name in APPROVED_PROVIDERS]
        if conflicts:
            raise ValueError(f"provider scopes already registered: {sorted(conflicts)}")
    for scope in scopes:
        register_provider_scope(scope, replace=replace)
    return names


def validate_provider_model(
    provider: str,
    model: str,
    region: str | None = None,
    classification: DataClassification = DataClassification.PUBLIC,
) -> tuple[bool, str]:
    scope = APPROVED_PROVIDERS.get(provider)
    if scope is None:
        return False, f"provider {provider!r} is not in configured approved scope"
    model_scope = scope.get_model_scope(model)
    if model_scope is None:
        return False, f"model {model!r} is not approved for provider {provider!r}"
    if not model_scope.alias_forbidden:
        return False, f"model {model!r} does not require immutable identity"
    if region is not None and not scope.allows_region(region):
        return False, f"region {region!r} is not supported by provider {provider!r}"
    if not scope.allows_classification(DataClassification(classification), model):
        return False, (
            f"data classification {DataClassification(classification).value!r} "
            f"is not permitted for {provider}/{model}"
        )
    return True, "approved"


def list_approved_models(provider: str | None = None) -> list[dict[str, Any]]:
    scopes: Iterable[ProviderScope]
    if provider is not None:
        selected = APPROVED_PROVIDERS.get(provider)
        scopes = (selected,) if selected is not None else ()
    else:
        scopes = tuple(APPROVED_PROVIDERS.values())

    result: list[dict[str, Any]] = []
    for scope in sorted(scopes, key=lambda item: item.provider_name):
        for model_id, model in sorted(scope.models.items()):
            result.append(
                {
                    "provider": scope.provider_name,
                    "model_id": model_id,
                    "tier": scope.tier.value,
                    "policy_version": scope.policy_version,
                    "regions": list(scope.regions),
                    "context_limit": model.context_limit,
                    "supports_tools": model.supports_tools,
                    "supports_json": model.supports_json,
                    "supports_streaming": model.supports_streaming,
                    "allowed_classifications": sorted(item.value for item in model.allowed_classifications),
                }
            )
    return result


def _load_environment_policy() -> None:
    policy_path = os.environ.get("WE3_PROVIDER_SCOPE_FILE", "").strip()
    if policy_path:
        load_provider_scope_file(policy_path)


_load_environment_policy()


__all__ = [
    "APPROVED_PROVIDERS",
    "DataClassification",
    "ModelScope",
    "ProviderScope",
    "ProviderTier",
    "list_approved_models",
    "load_provider_scope_file",
    "register_provider_scope",
    "validate_provider_model",
]
