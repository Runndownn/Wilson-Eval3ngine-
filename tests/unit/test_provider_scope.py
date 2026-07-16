"""Unit tests for Provider Scope Approval (TODO 24).

Tests cover:
- Provider/model allowlist validation
- Data classification policy evaluation
- Region restrictions
- Model scope attribute verification
- Experiment manifest validation against approved scope
"""


from wilson_eval3ngine.providers.scope import (
    APPROVED_PROVIDERS,
    DataClassification,
    ModelScope,
    ProviderScope,
    ProviderTier,
    validate_provider_model,
    list_approved_models,
)


class TestProviderScope:
    """Test suite for ProviderScope definition."""

    def test_approved_providers_defined(self):
        """Verify approved providers are defined."""
        assert "openai" in APPROVED_PROVIDERS
        assert "anthropic" in APPROVED_PROVIDERS

    def test_provider_scope_has_required_fields(self):
        """ProviderScope contains all required fields."""
        scope = APPROVED_PROVIDERS["openai"]

        assert scope.provider_name == "openai"
        assert scope.tier == ProviderTier.APPROVED
        assert len(scope.regions) > 0
        assert len(scope.models) > 0

    def test_model_scope_has_required_fields(self):
        """ModelScope contains all required metadata."""
        model_scope = APPROVED_PROVIDERS["openai"].models["gpt-4-turbo-2024-04-09"]

        assert model_scope.model_id == "gpt-4-turbo-2024-04-09"
        assert model_scope.alias_forbidden is True
        assert model_scope.context_limit > 0
        assert model_scope.input_token_price > 0
        assert model_scope.output_token_price > 0


class TestProviderModelAllowlist:
    """Test suite for provider/model allowlist validation."""

    def test_allows_approved_model(self):
        """Approved model returns valid status."""
        is_valid, reason = validate_provider_model(
            provider="openai",
            model="gpt-4-turbo-2024-04-09",
        )

        assert is_valid is True
        assert reason == "approved"

    def test_rejects_unapproved_provider(self):
        """Unapproved provider is rejected."""
        is_valid, reason = validate_provider_model(
            provider="unknown-provider",
            model="some-model",
        )

        assert is_valid is False
        assert "not in approved scope" in reason

    def test_rejects_unapproved_model(self):
        """Unapproved model is rejected."""
        is_valid, reason = validate_provider_model(
            provider="openai",
            model="gpt-3-unapproved",
        )

        assert is_valid is False
        assert "not approved" in reason

    def test_rejects_unapproved_region(self):
        """Unapproved region is rejected."""
        is_valid, reason = validate_provider_model(
            provider="openai",
            model="gpt-4-turbo-2024-04-09",
            region="ap-south-1",  # Not in approved regions
        )

        assert is_valid is False
        assert "not supported" in reason

    def test_allows_approved_region(self):
        """Approved region is accepted."""
        is_valid, reason = validate_provider_model(
            provider="openai",
            model="gpt-4-turbo-2024-04-09",
            region="us-east-1",
        )

        assert is_valid is True


class TestDataClassificationPolicy:
    """Test suite for data classification restrictions."""

    def test_public_classification_allowed(self):
        """Public classification allowed for all approved models."""
        is_valid, _ = validate_provider_model(
            provider="openai",
            model="gpt-4-turbo-2024-04-09",
            classification=DataClassification.PUBLIC,
        )
        assert is_valid is True

    def test_internal_classification_allowed(self):
        """Internal classification allowed for approved tier."""
        is_valid, _ = validate_provider_model(
            provider="openai",
            model="gpt-4-turbo-2024-04-09",
            classification=DataClassification.INTERNAL,
        )
        assert is_valid is True

    def test_experimental_provider_restrictions(self):
        """Experimental tier restricted to public classification."""
        # Create experimental scope inline
        experimental_scope = ProviderScope(
            provider_name="test-exp",
            tier=ProviderTier.EXPERIMENTAL,
            regions=["us-east-1"],
            models={
                "test-model": ModelScope(
                    model_id="test-model",
                    context_limit=8_000,
                ),
            },
        )

        # Should fail for restricted classification
        is_valid = experimental_scope.allows_classification(
            DataClassification.RESTRICTED, "test-model"
        )
        assert is_valid is False


class TestListApprovedModels:
    """Test suite for listing approved models."""

    def test_list_approved_models_all(self):
        """List all approved models."""
        models = list_approved_models()

        assert len(models) >= 4  # At least 4 models across providers

    def test_list_approved_models_by_provider(self):
        """List approved models for specific provider."""
        models = list_approved_models(provider="openai")

        assert len(models) >= 2
        for m in models:
            assert m["provider"] == "openai"


class TestExperimentManifestScopeValidation:
    """Test suite for ExperimentManifest scope validation."""

    def test_approved_models_accepted(self, foundation_manifest):
        """Experiment with approved models passes validation."""
        manifest_path = foundation_manifest
        from wilson_eval3ngine.domain.io import load_experiment

        # Foundation manifest uses mock provider which is now in approved scope
        manifest = load_experiment(manifest_path)

        assert manifest is not None
        assert len(manifest.models) >= 1

    def test_mock_provider_is_fallback_tier(self):
        """Mock provider is registered as fallback tier."""
        scope = APPROVED_PROVIDERS.get("mock")
        assert scope is not None
        assert scope.tier == ProviderTier.FALLBACK

    def test_unapproved_provider_model_rejected(self):
        """Experiment with unapproved provider/model is rejected."""
        # Create a minimal experiment manifest with unapproved model
        # This would fail at the contract level
        is_valid, reason = validate_provider_model(
            provider="unapproved-provider",
            model="unapproved-model",
        )
        assert is_valid is False


class TestModelIdentityRequirements:
    """Test suite for model identity verification requirements."""

    def test_alias_forbidden_by_default(self):
        """Model aliases are forbidden for safety."""
        model_scope = APPROVED_PROVIDERS["openai"].models["gpt-4-turbo-2024-04-09"]
        assert model_scope.alias_forbidden is True

    def test_identity_fingerprint_required(self):
        """Identity fingerprinting required for approved models."""
        model_scope = APPROVED_PROVIDERS["openai"].models["gpt-4-turbo-2024-04-09"]
        assert model_scope.requires_identity_fingerprint is True


class TestProviderAuthRequirements:
    """Test suite for provider authentication requirements."""

    def test_enterprise_auth_required(self):
        """Enterprise authentication required for production providers."""
        scope = APPROVED_PROVIDERS["openai"]
        assert scope.enterprise_auth_required is True
        assert scope.short_lived_credentials is True

    def test_processing_terms_required(self):
        """Processing terms required for data compliance."""
        scope = APPROVED_PROVIDERS["openai"]
        assert "EU Model Clauses" in scope.requires_processing_terms
        assert scope.training_use_prohibited is True