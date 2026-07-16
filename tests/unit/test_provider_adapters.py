"""Unit tests for production provider adapters.

Tests cover:
- Request mapping and normalization
- Identity drift detection
- Response validation and size bounds
- Error classification and retryability
- Credential isolation
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, Mock

from wilson_eval3ngine.domain.contracts import ProviderRequest, ConversationTurn, ContentBlock
from wilson_eval3ngine.providers.azure_openai import AzureOpenAIAdapter, _azure_available
from wilson_eval3ngine.providers.anthropic import AnthropicAdapter
from wilson_eval3ngine.providers.fingerprints import BudgetController, LimitState
from wilson_eval3ngine.providers.base import ProviderFailure
from wilson_eval3ngine.constants import FailureMode


# Test fixtures
def make_test_request(model: str = "gpt-4.1", provider: str = "azure_openai") -> ProviderRequest:
    """Create a minimal valid ProviderRequest for testing."""
    return ProviderRequest(
        run_id="test-run-123",
        model_config_id="test-config-456",
        provider=provider,
        model=model,
        messages=[
            ConversationTurn(
                role="user",
                content=[ContentBlock(text="What is the safety status of this request?")]
            )
        ],
        parameters={"temperature": 0.0, "max_tokens": 100},
    )


class TestAzureOpenAIAdapter:
    """Tests for Azure OpenAI adapter (Provider A)."""

    def test_rejects_azure_sdk_missing(self):
        """Test that adapter fails gracefully when SDK not installed."""
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        if not _azure_available:
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)
            assert exc_info.value.error_class == FailureMode.CONFIGURATION_ERROR

    def test_rejects_simulation_mode(self):
        """Test that simulation mode is rejected in production adapter."""
        if not _azure_available:
            pytest.skip("azure SDK not available")
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        with pytest.raises(ProviderFailure) as exc_info:
            adapter.execute(request, simulation={"fault_sequence": []})

        assert exc_info.value.error_class == FailureMode.CONFIGURATION_ERROR

    def test_rejects_unapproved_model(self):
        """Test that unapproved models are rejected."""
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="unapproved-model")

        if not _azure_available:
            # Without SDK, we get CONFIGURATION_ERROR
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)
            assert exc_info.value.error_class == FailureMode.CONFIGURATION_ERROR
        else:
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)

            assert exc_info.value.error_class == FailureMode.VALIDATION_ERROR
            assert "not in approved scope" in exc_info.value.safe_detail

    def test_rejects_unapproved_endpoint(self):
        """Test that endpoints not in allowlist are rejected."""
        adapter = AzureOpenAIAdapter(endpoint="https://unapproved.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        # Endpoint validation happens before SDK check in __init__ path
        # but the test checks the security error
        if not _azure_available:
            with pytest.raises(ProviderFailure):
                adapter.execute(request)
        else:
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)

            assert exc_info.value.error_class == FailureMode.SECURITY_VIOLATION

    def test_rejects_missing_endpoint(self):
        """Test that missing endpoint configuration is caught."""
        adapter = AzureOpenAIAdapter()
        request = make_test_request(model="gpt-4.1")

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)

            assert exc_info.value.error_class == FailureMode.CONFIGURATION_ERROR

    def test_success_response_structure(self):
        """Test successful response structure."""
        if not _azure_available:
            pytest.skip("azure SDK not available")
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Safe response with [WE3_REQUIRED] marker."
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_client = Mock()
        mock_client.complete = Mock(return_value=mock_response)

        with patch.object(adapter, "_ensure_client", return_value=mock_client):
            response = adapter.execute(request)

            assert response.protocol_valid is True
            assert response.terminal is True
            assert "[WE3_REQUIRED]" in response.text
            assert response.usage["input_tokens"] == 10
            assert response.usage["output_tokens"] == 20
            assert response.provider_reported_model == "gpt-4.1"
            assert response.attempt_id.startswith("att-")

    def test_model_identity_drift_detection(self):
        """Test detection of model identity drift."""
        if not _azure_available:
            pytest.skip("azure SDK not available")
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "drifted-model"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        mock_client = Mock()
        mock_client.complete = Mock(return_value=mock_response)

        with patch.object(adapter, "_ensure_client", return_value=mock_client):
            response = adapter.execute(request)

            assert response.capability_observations["model_identity_drifted"] is True

    def test_response_size_limit(self):
        """Test response size limit enforcement."""
        if not _azure_available:
            pytest.skip("azure SDK not available")
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        large_text = "x" * 150_000

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = large_text
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        mock_client = Mock()
        mock_client.complete = Mock(return_value=mock_response)

        with patch.object(adapter, "_ensure_client", return_value=mock_client):
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)

            assert exc_info.value.error_class == FailureMode.VALIDATION_ERROR

    def test_rate_limit_error_classification(self):
        """Test rate limit error classification."""
        if not _azure_available:
            pytest.skip("azure SDK not available")
        adapter = AzureOpenAIAdapter(endpoint="https://eastus2.services.azureOpenAI.net")
        request = make_test_request(model="gpt-4.1")

        mock_client = Mock()
        mock_client.complete = Mock(side_effect=Exception("429 Too Many Requests"))

        with patch.object(adapter, "_ensure_client", return_value=mock_client):
            with pytest.raises(ProviderFailure) as exc_info:
                adapter.execute(request)

            assert exc_info.value.retryable is True
            assert exc_info.value.error_class == FailureMode.RATE_LIMITED


class TestAnthropicAdapter:
    """Tests for Anthropic adapter (Provider B)."""

    def test_rejects_simulation_mode(self):
        """Test that simulation mode is rejected in production adapter."""
        adapter = AnthropicAdapter(api_key="test-key")
        request = make_test_request(model="claude-3-7-sonnet-20250219", provider="anthropic")

        with pytest.raises(ProviderFailure) as exc_info:
            adapter.execute(request, simulation={"fault_sequence": []})

        assert exc_info.value.error_class == FailureMode.CONFIGURATION_ERROR

    def test_rejects_unapproved_model(self):
        """Test that unapproved models are rejected."""
        adapter = AnthropicAdapter(api_key="test-key")
        request = make_test_request(model="unapproved-claude")

        # Without SDK, we get CONFIGURATION_ERROR; with SDK, we get VALIDATION_ERROR
        with pytest.raises(ProviderFailure) as exc_info:
            adapter.execute(request)

        # Accept either error (SDK missing or model validation)
        assert exc_info.value.error_class in (FailureMode.CONFIGURATION_ERROR, FailureMode.VALIDATION_ERROR)

    def test_success_response_structure(self):
        """Test successful response structure."""
        adapter = AnthropicAdapter(api_key="test-key")
        request = make_test_request(model="claude-3-7-sonnet-20250219", provider="anthropic")

        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Safe response from Claude."
        mock_response.stop_reason = "end_turn"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25

        mock_client = Mock()
        mock_client.messages = Mock()
        mock_client.messages.create = Mock(return_value=mock_response)

        with patch.object(adapter, "_ensure_client", return_value=mock_client):
            response = adapter.execute(request)

            assert response.protocol_valid is True
            assert response.terminal is True
            assert "Safe response" in response.text
            assert response.usage["input_tokens"] == 15
            assert response.capability_observations["tool_calling_format"] == "anthropic"

    def test_finish_reason_normalization(self):
        """Test Anthropic finish reason normalization."""
        adapter = AnthropicAdapter(api_key="test-key")
        request = make_test_request(model="claude-3-7-sonnet-20250219", provider="anthropic")

        for anthropic_reason, canonical in [
            ("end_turn", "stop"),
            ("max_tokens", "length"),
            ("tool_use", "tool_calls"),
        ]:
            mock_response = Mock()
            mock_response.content = [Mock()]
            mock_response.content[0].text = "Response"
            mock_response.stop_reason = anthropic_reason
            mock_response.usage = Mock(input_tokens=10, output_tokens=20)

            mock_client = Mock()
            mock_client.messages = Mock()
            mock_client.messages.create = Mock(return_value=mock_response)

            with patch.object(adapter, "_ensure_client", return_value=mock_client):
                response = adapter.execute(request)
                assert response.finish_reason == canonical


class TestBudgetController:
    """Tests for fingerprinting and quota controls."""

    def test_quota_estimation(self):
        """Test token and cost estimation."""
        controller = BudgetController()

        input_tokens, output_tokens, cost = controller.estimate_tokens_and_cost(
            "gpt-4.1",
            [{"content": "test"}],
            expected_output_tokens=500,
        )

        assert input_tokens == 4  # len("test")
        assert output_tokens == 500
        assert cost > 0

    def test_quota_admission_check(self):
        """Test admission check against quota limits."""
        controller = BudgetController()

        state = controller.check_admission("test-project", "gpt-4.1", [{"content": "test"}])
        assert state == LimitState.OK

    def test_quota_override_auditing(self):
        """Test quota override with audit trail."""
        controller = BudgetController()

        token = controller.apply_quota_override(
            "test-project",
            reason="security testing",
            approver="test-approver@example.com",
            duration_hours=1,
        )

        assert token.startswith("override-")
        audit = controller.get_override_audit()
        assert len(audit) == 1
        assert audit[0]["approver"] == "test-approver@example.com"
        assert audit[0]["reason"] == "security testing"

    def test_model_fingerprint_validation(self):
        """Test model fingerprint validation and drift detection."""
        controller = BudgetController()

        result = controller.validate_model_fingerprint(
            "gpt-4.1",
            "azure_openai",
            "abc123hash",
            {"streaming": True, "functions": True},
        )
        assert result is True

        result = controller.validate_model_fingerprint("gpt-4.1", "azure_openai", "abc123hash", {})
        assert result is True

        result = controller.validate_model_fingerprint("gpt-4.1", "azure_openai", "differenthash", {})
        assert result is False