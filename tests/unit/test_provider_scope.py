"""Provider scope policy tests.

Real provider approval is explicit governance input; only deterministic mock scope
is built into source.
"""

from __future__ import annotations

import json

import pytest

from wilson_eval3ngine.providers.scope import (
    APPROVED_PROVIDERS,
    DataClassification,
    ModelScope,
    ProviderScope,
    ProviderTier,
    list_approved_models,
    load_provider_scope_file,
    register_provider_scope,
    validate_provider_model,
)


def _real_scope(name: str = "vendor-test") -> ProviderScope:
    model = ModelScope(
        model_id="model-2026-08-22",
        context_limit=32_000,
        supports_json=True,
        allowed_classifications=frozenset(
            {DataClassification.PUBLIC, DataClassification.INTERNAL}
        ),
    )
    return ProviderScope(
        provider_name=name,
        tier=ProviderTier.APPROVED,
        regions=("region-a",),
        models={model.model_id: model},
        processing_terms_ref="policy://legal/provider-v3",
        retention_days=0,
        policy_version="provider-policy-2026-08-22",
    )


def test_source_only_approves_deterministic_mock() -> None:
    assert set(APPROVED_PROVIDERS) == {"mock"}
    scope = APPROVED_PROVIDERS["mock"]
    assert scope.tier == ProviderTier.FALLBACK
    assert scope.policy_version == "builtin-mock-v1"


def test_real_provider_fails_closed_until_explicitly_registered(monkeypatch) -> None:
    valid, reason = validate_provider_model("vendor-test", "model-2026-08-22")
    assert valid is False
    assert "configured approved scope" in reason

    scope = _real_scope()
    monkeypatch.setitem(APPROVED_PROVIDERS, scope.provider_name, scope)
    valid, reason = validate_provider_model(
        "vendor-test",
        "model-2026-08-22",
        region="region-a",
        classification=DataClassification.INTERNAL,
    )
    assert valid is True
    assert reason == "approved"


def test_model_identity_and_region_are_exact(monkeypatch) -> None:
    scope = _real_scope()
    monkeypatch.setitem(APPROVED_PROVIDERS, scope.provider_name, scope)

    assert validate_provider_model("vendor-test", "model-latest")[0] is False
    assert validate_provider_model(
        "vendor-test", "model-2026-08-22", region="region-b"
    )[0] is False


def test_classification_policy_is_model_data_not_vendor_name_logic(monkeypatch) -> None:
    scope = _real_scope()
    monkeypatch.setitem(APPROVED_PROVIDERS, scope.provider_name, scope)

    assert validate_provider_model(
        "vendor-test",
        "model-2026-08-22",
        classification=DataClassification.PUBLIC,
    )[0] is True
    assert validate_provider_model(
        "vendor-test",
        "model-2026-08-22",
        classification=DataClassification.RESTRICTED,
    )[0] is False


def test_experimental_scope_can_be_explicitly_public_only() -> None:
    model = ModelScope(
        model_id="exp-model-v1",
        allowed_classifications=frozenset({DataClassification.PUBLIC}),
    )
    scope = ProviderScope(
        provider_name="experimental",
        tier=ProviderTier.EXPERIMENTAL,
        regions=("lab",),
        models={model.model_id: model},
        policy_version="lab-v1",
    )

    assert scope.allows_classification(DataClassification.PUBLIC, model.model_id) is True
    assert scope.allows_classification(DataClassification.INTERNAL, model.model_id) is False


def test_provider_scope_is_immutable_at_nested_mapping_boundary() -> None:
    scope = _real_scope()
    with pytest.raises(TypeError):
        scope.models["other"] = ModelScope(model_id="other")  # type: ignore[index]


def test_conflicting_registration_requires_explicit_replace(monkeypatch) -> None:
    scope = _real_scope()
    monkeypatch.setitem(APPROVED_PROVIDERS, scope.provider_name, scope)
    changed = ProviderScope(
        provider_name=scope.provider_name,
        tier=scope.tier,
        regions=scope.regions,
        models=scope.models,
        policy_version="provider-policy-v2",
    )

    with pytest.raises(ValueError, match="already registered"):
        register_provider_scope(changed)


def test_versioned_policy_file_loads_as_complete_batch(tmp_path, monkeypatch) -> None:
    # Isolate global registry modifications from the rest of the suite.
    monkeypatch.setattr(
        "wilson_eval3ngine.providers.scope.APPROVED_PROVIDERS",
        {"mock": APPROVED_PROVIDERS["mock"]},
    )
    policy = {
        "schema_version": "we3.provider_scope.v1",
        "providers": [
            {
                "provider_name": "vendor-file",
                "tier": "approved",
                "policy_version": "policy-file-v1",
                "regions": ["region-a"],
                "processing_terms_ref": "policy://legal/v1",
                "retention_days": 0,
                "models": [
                    {
                        "model_id": "exact-model-v1",
                        "context_limit": 8192,
                        "allowed_classifications": ["public"],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "provider-scope.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    names = load_provider_scope_file(path)

    assert names == ["vendor-file"]
    assert validate_provider_model("vendor-file", "exact-model-v1")[0] is True


def test_policy_file_rejects_unknown_schema_without_partial_registration(
    tmp_path, monkeypatch
) -> None:
    isolated = {"mock": APPROVED_PROVIDERS["mock"]}
    monkeypatch.setattr("wilson_eval3ngine.providers.scope.APPROVED_PROVIDERS", isolated)
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "we3.provider_scope.v999",
                "providers": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported"):
        load_provider_scope_file(path)
    assert set(isolated) == {"mock"}


def test_list_models_exposes_policy_version_not_fake_price_or_approval(monkeypatch) -> None:
    scope = _real_scope()
    monkeypatch.setitem(APPROVED_PROVIDERS, scope.provider_name, scope)
    records = list_approved_models("vendor-test")

    assert records == [
        {
            "provider": "vendor-test",
            "model_id": "model-2026-08-22",
            "tier": "approved",
            "policy_version": "provider-policy-2026-08-22",
            "regions": ["region-a"],
            "context_limit": 32000,
            "supports_tools": False,
            "supports_json": True,
            "supports_streaming": False,
            "allowed_classifications": ["internal", "public"],
        }
    ]


def test_foundation_manifest_still_uses_source_controlled_mock(foundation_manifest) -> None:
    from wilson_eval3ngine.domain.io import load_experiment

    manifest = load_experiment(foundation_manifest)
    assert manifest.models
    assert all(model.provider == "mock" for model in manifest.models)
