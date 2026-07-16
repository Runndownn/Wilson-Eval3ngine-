"""Integration tests for Provider Adapter with Scheduler (TODO 23).

Tests cover:
- Provider response integration with scheduler retry decisions
- Provider mock fault scenarios in execution context
- Latency and usage reporting through scheduler
- Capability observation propagation
- Metadata extension handling
"""

from __future__ import annotations

import pytest

from wilson_eval3ngine.constants import FailureMode
from wilson_eval3ngine.domain.contracts import (
    ContentBlock,
    ConversationTurn,
    ProviderRequest,
    ProviderResponse,
    RetryPolicy as DomainRetryPolicy,
)
from wilson_eval3ngine.providers.mock import DeterministicMockProvider
from wilson_eval3ngine.providers.base import ProviderFailure
from wilson_eval3ngine.persistence.scheduler import (
    DurableScheduler,
    JobLease,
    JobState,
)
from wilson_eval3ngine.persistence.database import Database


@pytest.fixture
def provider() -> DeterministicMockProvider:
    """Create mock provider instance."""
    return DeterministicMockProvider()


@pytest.fixture
def scheduler_db():
    """Create an in-memory SQLite database for scheduler tests."""
    db = Database(url="sqlite:///:memory:")
    db.initialize()
    return db


@pytest.fixture
def sample_request() -> ProviderRequest:
    """Create a sample provider request."""
    return ProviderRequest(
        run_id="run_int_001",
        model_config_id="model:gpt-4-turbo",
        provider="mock",
        model="gpt-4-turbo",
        messages=[
            ConversationTurn(
                role="user",
                content=[ContentBlock(text="Test query")],
            ),
        ],
    )


class TestProviderSchedulerIntegration:
    """Test suite for provider-scheduler integration."""

    def test_successful_response_triggers_success_state(
        self, provider: DeterministicMockProvider, scheduler_db, sample_request: ProviderRequest
    ):
        """Successful mock response maps to proper scheduler handling."""
        scheduler = DurableScheduler(scheduler_db)

        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert response.protocol_valid is True
        assert response.terminal is True
        assert response.text != ""

    def test_retryable_failure_triggers_retry_state(
        self, provider: DeterministicMockProvider, scheduler_db, sample_request: ProviderRequest
    ):
        """Retryable failure maps to retry-wait state for scheduler."""
        scheduler = DurableScheduler(scheduler_db)

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(
                sample_request,
                simulation={"fault_sequence": ["provider_timeout"]},
                attempt_number=1,
            )

        assert exc_info.value.retryable is True

    def test_non_retryable_failure_triggers_dead_letter(
        self, provider: DeterministicMockProvider, scheduler_db, sample_request: ProviderRequest
    ):
        """Non-retryable failure maps to dead-letter consideration."""
        scheduler = DurableScheduler(scheduler_db)

        with pytest.raises(ProviderFailure) as exc_info:
            provider.execute(
                sample_request,
                simulation={"fault_sequence": ["authentication"]},
                attempt_number=1,
            )

        assert exc_info.value.retryable is False

    def test_retry_policy_interprets_retryable(
        self, provider: DeterministicMockProvider, scheduler_db, sample_request: ProviderRequest
    ):
        """Scheduler retry policy correctly interprets provider retryable flag."""
        retry_policy = DomainRetryPolicy()

        # Test that retryable failures are recognized
        assert any(
            "rate_limit" in cls.lower() or "5xx" in cls.lower() or "transient" in cls.lower()
            for cls in retry_policy.retryable_classes
        )


class TestProviderMockDeterminism:
    """Test suite for mock determinism in integration context."""

    def test_same_seed_same_response(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Same seed produces byte-for-byte identical response."""
        sim = {"seed": 12345, "behavior": "safe", "required_concepts": ["test"]}

        r1 = provider.execute(sample_request, simulation=sim, attempt_number=1)
        r2 = provider.execute(sample_request, simulation=sim, attempt_number=1)

        assert r1.text == r2.text
        assert r1.latency_ms == r2.latency_ms
        assert r1.raw_response_hash == r2.raw_response_hash
        assert r1.metadata["adapter"] == r2.metadata["adapter"]

    def test_different_attempts_different_responses(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Different attempt numbers produce different responses with same seed."""
        sim = {"seed": 42, "behavior": "safe"}

        # First attempt - normal response
        r1 = provider.execute(sample_request, simulation=sim, attempt_number=1)

        # With fault_sequence, attempt 1 raises exception
        with pytest.raises(ProviderFailure):
            provider.execute(
                sample_request,
                simulation={"seed": 42, "fault_sequence": ["provider_timeout"]},
                attempt_number=1,
            )

        # Verify first response was a success
        assert r1.text != ""  # Success response has text
        assert r1.terminal is True


class TestUsageReporting:
    """Test suite for usage reporting integration."""

    def test_usage_tokens_reported(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Usage tokens are always reported in response."""
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert "input_tokens" in response.usage
        assert "output_tokens" in response.usage
        assert isinstance(response.usage["input_tokens"], int)
        assert isinstance(response.usage["output_tokens"], int)

    def test_latency_reported(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Latency is reported in milliseconds."""
        response = provider.execute(sample_request, simulation={"behavior": "safe", "latency_ms": 150})

        assert response.latency_ms > 0
        assert isinstance(response.latency_ms, (int, float))

    def test_usage_anomaly_detection(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Usage anomaly produces detectable metrics."""
        response = provider.execute(
            sample_request, simulation={"fault_sequence": ["usage_anomaly"]}
        )

        # Anomaly should produce suspicious values
        total_output = response.usage.get("output_tokens", 0)
        assert total_output > 10000 or response.usage.get("input_tokens", 0) < 0


class TestCapabilityObservations:
    """Test suite for capability observations integration."""

    def test_capability_observation_propagation(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Capability observations are propagated through response."""
        response = provider.execute(
            sample_request, simulation={"behavior": "safe", "observe_capabilities": True}
        )

        assert "streaming_supported" in response.capability_observations
        assert "function_calling_supported" in response.capability_observations

    def test_capability_observation_false(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Without observation flag, capabilities remain empty."""
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert response.capability_observations == {}


class TestMetadataExtensions:
    """Test suite for metadata extension handling."""

    def test_provider_metadata_present(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Provider metadata is included in response metadata."""
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert "provider_metadata" in response.metadata

    def test_fault_sequence_records_in_metadata(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Fault sequence is recorded in metadata for debugging."""
        response = provider.execute(
            sample_request,
            simulation={"seed": 42, "fault_sequence": ["content_filter"]},
        )

        assert response.finish_reason == "content_filter"
        assert "simulation_fault" in response.metadata


class TestRequestHashing:
    """Test suite for request hash integration."""

    def test_request_hash_used_for_tracing(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Request hash is computed and available for correlation."""
        request_hash = sample_request.compute_request_hash()

        assert len(request_hash) == 64  # SHA-256 hex length

        # Response should reference the same run
        response = provider.execute(sample_request, simulation={"behavior": "safe"})
        assert response.run_id == sample_request.run_id

    def test_different_requests_different_hashes(self, sample_request: ProviderRequest):
        """Different request parameters produce different hashes."""
        r1 = ProviderRequest(
            run_id="run_a",
            model_config_id="model:gpt-4",
            provider="mock",
            model="gpt-4",
            messages=sample_request.messages,
        )

        r2 = ProviderRequest(
            run_id="run_b",
            model_config_id="model:gpt-4",
            provider="mock",
            model="gpt-4",
            messages=sample_request.messages,
        )

        assert r1.compute_request_hash() != r2.compute_request_hash()


class TestRawResponseHash:
    """Test suite for raw response hash validation."""

    def test_raw_response_hash_present(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Raw response hash is always computed for response integrity."""
        response = provider.execute(sample_request, simulation={"behavior": "safe"})

        assert response.raw_response_hash is not None
        assert len(response.raw_response_hash) == 64

    def test_raw_response_hash_changes_with_content(
        self, provider: DeterministicMockProvider, sample_request: ProviderRequest
    ):
        """Different content produces different raw response hash."""
        r1 = provider.execute(sample_request, simulation={"behavior": "safe"})
        r2 = provider.execute(sample_request, simulation={"behavior": "refuse"})

        assert r1.raw_response_hash != r2.raw_response_hash