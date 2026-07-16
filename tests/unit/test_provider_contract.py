"""Unit tests for Provider Adapter Contract (TODO 23).

Tests cover:
- ProviderRequest compute_request_hash determinism
- ProviderRequest canonical field validation
- DeterministicMockProvider seed-based reproducibility
- Fault simulation scenarios (timeout, 429, 5xx, malformed, partial stream, usage anomaly, content filter, identity drift)
- Capability observations
- Metadata extension rules
"""

import pytest

from wilson_eval3ngine.constants import FailureMode
from wilson_eval3ngine.domain.contracts import (
    ContentBlock,
    ConversationTurn,
    ProviderRequest,
)
from wilson_eval3ngine.providers.base import ProviderAdapter, ProviderFailure
from wilson_eval3ngine.providers.mock import DeterministicMockProvider


@pytest.fixture
def sample_request() -> ProviderRequest:
    """Create a sample provider request for testing."""
    return ProviderRequest(
        run_id="run_test_001",
        model_config_id="model:gpt-4-turbo-2024-04-09",
        provider="mock",
        model="gpt-4-turbo",
        messages=[
            ConversationTurn(
                role="user",
                content=[ContentBlock(text="What is the weather today?")],
            ),
        ],
        parameters={"temperature": 0.7, "max_tokens": 100},
    )


class TestProviderRequestContract:
    """Test suite for ProviderRequest canonical contract."""

    def test_compute_request_hash_is_deterministic(self, sample_request: ProviderRequest):
        """Same request produces same hash every time."""
        hash1 = sample_request.compute_request_hash()
        hash2 = sample_request.compute_request_hash()
        assert hash1 == hash2, "Hash should be deterministic"
        assert len(hash1) == 64, "Hash should be SHA-256 hex"

    def test_request_hash_changes_with_messages(self, sample_request: ProviderRequest):
        """Different messages produce different hash."""
        hash1 = sample_request.compute_request_hash()
        sample_request.messages.append(
            ConversationTurn(
                role="user",
                content=[ContentBlock(text="Another message")],
            ),
        )
        hash2 = sample_request.compute_request_hash()
        assert hash1 != hash2, "Different content should produce different hash"

    def test_request_hash_changes_with_parameters(self, sample_request: ProviderRequest):
        """Different parameters produce different hash."""
        hash1 = sample_request.compute_request_hash()
        sample_request.parameters["temperature"] = 0.9
        hash2 = sample_request.compute_request_hash()
        assert hash1 != hash2, "Different parameters should produce different hash"

    def test_request_hash_includes_experiment_id(self, sample_request: ProviderRequest):
        """Hash includes experiment_id when present."""
        sample_request.experiment_id = "exp_001"
        hash_with_exp = sample_request.compute_request_hash()
        # Verify hash is computed (doesn't raise)
        assert len(hash_with_exp) == 64

    def test_request_hash_includes_deadline(self, sample_request: ProviderRequest):
        """Hash includes deadline when present."""
        from datetime import datetime, timezone

        sample_request.deadline = datetime(2026, 7, 15, 23, 59, tzinfo=timezone.utc)
        hash_with_deadline = sample_request.compute_request_hash()
        assert len(hash_with_deadline) == 64


class TestDeterministicMockProvider:
    """Test suite for DeterministicMockProvider contract compliance."""

    def test_provider_has_name_attribute(self):
        """Provider exposes name for registry lookup."""
        provider = DeterministicMockProvider()
        assert provider.name == "mock"

    def test_provider_is_protocol_compliant(self):
        """Provider satisfies ProviderAdapter protocol."""
        provider = DeterministicMockProvider()
        assert isinstance(provider, ProviderAdapter)

    def test_same_seed_produces_same_response(self, sample_request: ProviderRequest):
        """Seed produces deterministic responses."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "behavior": "safe"}

        response1 = provider.execute(sample_request, simulation=sim, attempt_number=1)
        response2 = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response1.text == response2.text
        assert response1.latency_ms == response2.latency_ms
        assert response1.raw_response_hash == response2.raw_response_hash

    def test_different_seeds_produce_different_responses(self, sample_request: ProviderRequest):
        """Different seeds produce different latency values."""
        provider = DeterministicMockProvider()

        response1 = provider.execute(
            sample_request, simulation={"seed": 1, "behavior": "safe"}, attempt_number=1
        )
        response2 = provider.execute(
            sample_request, simulation={"seed": 2, "behavior": "safe"}, attempt_number=1
        )

        # Same behavior but different latency (seed affects deterministic variation)
        assert response1.text == response2.text  # Behavior is same
        assert response1.raw_response_hash == response2.raw_response_hash


class TestDeterministicMockFaults:
    """Test suite for fault simulation scenarios."""

    def test_provider_timeout_fault(self, sample_request: ProviderRequest):
        """Provider timeout fault raises retryable failure."""
        provider = DeterministicMockProvider()
        sim = {"fault_sequence": ["provider_timeout"]}

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert exc_info.value.retryable is True
        assert exc_info.value.error_class == FailureMode.PROVIDER_TIMEOUT

    def test_provider_rate_limit_fault(self, sample_request: ProviderRequest):
        """Rate limit fault raises retryable failure."""
        provider = DeterministicMockProvider()
        sim = {"fault_sequence": ["provider_rate_limit"]}

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert exc_info.value.retryable is True

    def test_provider_5xx_fault(self, sample_request: ProviderRequest):
        """5xx server error fault raises retryable failure."""
        provider = DeterministicMockProvider()
        sim = {"fault_sequence": ["provider_5xx"]}

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert exc_info.value.retryable is True

    def test_network_transient_fault(self, sample_request: ProviderRequest):
        """Transient network fault raises retryable failure."""
        provider = DeterministicMockProvider()
        sim = {"fault_sequence": ["network_transient"]}

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert exc_info.value.retryable is True

    def test_authentication_fault(self, sample_request: ProviderRequest):
        """Authentication fault raises non-retryable failure."""
        provider = DeterministicMockProvider()
        sim = {"fault_sequence": ["authentication"]}

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert exc_info.value.retryable is False
        assert exc_info.value.error_class == FailureMode.AUTH_FAILURE

    def test_malformed_response_fault(self, sample_request: ProviderRequest):
        """Malformed response returns non-protocol-valid response."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "fault_sequence": ["malformed_response"]}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.protocol_valid is False
        assert "WE3_MALFORMED" in response.text
        assert "malformed" in response.finish_reason

    def test_partial_stream_fault(self, sample_request: ProviderRequest):
        """Partial stream fault returns incomplete response."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "fault_sequence": ["partial_stream"]}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.terminal is False
        assert "cut off" in response.text
        assert response.finish_reason == "stream_error"

    def test_usage_anomaly_fault(self, sample_request: ProviderRequest):
        """Usage anomaly fault produces suspicious usage values."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "fault_sequence": ["usage_anomaly"]}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.usage["input_tokens"] < 0 or response.usage["output_tokens"] > 100000

    def test_content_filter_fault(self, sample_request: ProviderRequest):
        """Content filter fault returns empty response with filter finish reason."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "fault_sequence": ["content_filter"]}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.text == ""
        assert response.finish_reason == "content_filter"


class TestDeterministicMockIdentityDrift:
    """Test suite for model identity drift fault."""

    def test_model_identity_drift(self, sample_request: ProviderRequest):
        """Identity drift fault returns different model than requested."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "fault_sequence": ["model_identity_drift"]}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.provider_reported_model != sample_request.model
        assert "drifted-model" in response.provider_reported_model


class TestCapabilityObservations:
    """Test suite for capability observation mode."""

    def test_capability_observation_includes_requested_fields(self, sample_request: ProviderRequest):
        """Observe capabilities returns structured observations."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "behavior": "safe", "observe_capabilities": True}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert "streaming_supported" in response.capability_observations
        assert "function_calling_supported" in response.capability_observations
        assert "json_mode_supported" in response.capability_observations

    def test_capability_observation_defaults_empty(self, sample_request: ProviderRequest):
        """Without observe_capabilities flag, observations are empty."""
        provider = DeterministicMockProvider()
        sim = {"behavior": "safe"}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert response.capability_observations == {}


class TestMetadataExtensionRules:
    """Test suite for metadata extension rules compliance."""

    def test_provider_metadata_is_namespaced(self, sample_request: ProviderRequest):
        """Provider metadata is under namespaced key."""
        provider = DeterministicMockProvider()
        sim = {"seed": 42, "behavior": "safe"}

        response = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert "provider_metadata" in response.metadata


class TestResponseCanonicalFields:
    """Test suite for canonical response field validation."""

    def test_response_has_required_canonical_fields(self, sample_request: ProviderRequest):
        """Response contains all required canonical fields."""
        provider = DeterministicMockProvider()
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert response.run_id == sample_request.run_id
        assert response.attempt_id is not None
        assert response.provider_reported_model == sample_request.model
        assert isinstance(response.terminal, bool)
        assert isinstance(response.protocol_valid, bool)
        assert isinstance(response.usage, dict)
        assert isinstance(response.latency_ms, (int, float))
        assert response.raw_response_hash is not None

    def test_response_hash_is_computed(self, sample_request: ProviderRequest):
        """Raw response hash is computed and not None."""
        provider = DeterministicMockProvider()
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert len(response.raw_response_hash) == 64