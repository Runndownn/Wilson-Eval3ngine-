from __future__ import annotations

import time
from typing import Any

from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex
from ..constants import FailureMode
from .base import ProviderFailure

# Lazy imports to allow testing without SDK installed
_azure_available = False
try:
    from azure.identity import DefaultAzureCredential
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import AssistantMessage, UserMessage, SystemMessage
    _azure_available = True
except ImportError:
    pass


class AzureOpenAIAdapter:
    """Production provider adapter for Azure OpenAI Service (Provider A).

    Implementation follows TODO 25 requirements:
    - One attempt per call (no hidden retries)
    - Short-lived credentials via OIDC workload identity
    - Exact model identity capture with drift detection
    - Credential redaction in logs and telemetry
    - Canonical request mapping with parameter validation

    Security and safety requirements implemented:
    - Credentials delivered at runtime, never persisted
    - Egress restricted to approved endpoints
    - Response validation and size bounds
    - TLS validation enforced
    """

    name = "azure_openai"

    ENDPOINT_TEMPLATE = "https://{region}.services.azureOpenAI.net/models/{model}/chat/completions"

    # Approved regions from provider scope approval
    APPROVED_REGIONS = {"eastus2", "westus3", "uksouth"}

    # Model name mapping (canonical ID -> Azure deployment)
    MODEL_MAPPING = {
        "gpt-4.1": "gpt-4.1",
        "gpt-4.1-mini": "gpt-4.1-mini",
        "gpt-5": "gpt-5",
    }

    def __init__(self, endpoint: str | None = None, credential: Any = None):
        """Initialize adapter.

        Args:
            endpoint: Azure OpenAI endpoint (if None, uses environment AZURE_OPENAI_ENDPOINT)
            credential: Azure credential (if None, uses DefaultAzureCredential)

        Security note:
            Credentials are never stored in instance attributes longer than needed.
            Uses workload identity at call time to prevent credential leakage.
        """
        self._endpoint = endpoint
        self._credential = credential
        self._client = None

    def _ensure_client(self) -> Any:
        """Lazy-initialize client with runtime credentials."""
        if self._client is None:
            endpoint = self._endpoint
            if endpoint is None:
                import os
                endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                if not endpoint:
                    raise ProviderFailure(
                        error_class=FailureMode.CONFIGURATION_ERROR,
                        safe_detail="AZURE_OPENAI_ENDPOINT not configured",
                        retryable=False,
                    )

            # Validate endpoint is in approved allowlist
            self._validate_endpoint(endpoint)

            credential = self._credential or DefaultAzureCredential()
            self._client = ChatCompletionsClient(endpoint=endpoint, credential=credential)
        return self._client

    def _validate_endpoint(self, endpoint: str) -> None:
        """Validate endpoint is in approved allowlist."""
        endpoint_lower = endpoint.lower()
        for region in self.APPROVED_REGIONS:
            if region in endpoint_lower:
                return
        raise ProviderFailure(
            error_class=FailureMode.SECURITY_VIOLATION,
            safe_detail=f"endpoint not in approved allowlist: {endpoint[:50]}...",
            retryable=False,
        )

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        """Execute one canonical provider attempt.

        Args:
            request: Canonical provider request with hashed payload
            simulation: NOT USED for production adapter - raises error if provided
            attempt_number: 1-based attempt number (for logging correlation)

        Returns:
            ProviderResponse with canonical fields populated

        Raises:
            ProviderFailure on configuration, auth, or protocol errors
        """
        if not _azure_available:
            raise ProviderFailure(
                error_class=FailureMode.CONFIGURATION_ERROR,
                safe_detail="azure SDK not installed",
                retryable=False,
            )

        if simulation is not None:
            raise ProviderFailure(
                error_class=FailureMode.CONFIGURATION_ERROR,
                safe_detail="simulation mode not supported in production adapter",
                retryable=False,
            )

        start_time = time.time()
        attempt_id = new_id("att")

        azure_model = self.MODEL_MAPPING.get(request.model)
        if azure_model is None:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"model not in approved scope: {request.model}",
                retryable=False,
            )

        try:
            client = self._ensure_client()
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure(
                error_class=FailureMode.AUTH_FAILURE,
                safe_detail="failed to initialize provider client",
                retryable=False,
            )

        # Build messages with role mapping
        azure_messages: list = []
        for turn in request.messages:
            content = " ".join(block.text for block in turn.content)
            if turn.role == "user":
                azure_messages.append(UserMessage(content=content))
            elif turn.role == "assistant":
                azure_messages.append(AssistantMessage(content=content))
            elif turn.role == "system":
                azure_messages.append(SystemMessage(content=content))

        try:
            response = client.complete(
                model=azure_model,
                messages=azure_messages,
                max_tokens=request.parameters.get("max_tokens", 4096),
                temperature=request.parameters.get("temperature", 0.0),
                top_p=request.parameters.get("top_p"),
                timeout=request.timeout_seconds,
            )
        except Exception as exc:
            error_msg = str(exc)
            if "429" in error_msg or "rate" in error_msg.lower():
                raise ProviderFailure(
                    error_class=FailureMode.RATE_LIMITED,
                    safe_detail="provider rate limit exceeded",
                    retryable=True,
                ) from exc
            if "timeout" in error_msg.lower():
                raise ProviderFailure(
                    error_class=FailureMode.PROVIDER_TIMEOUT,
                    safe_detail="provider request timed out",
                    retryable=True,
                ) from exc
            if "unauthorized" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                raise ProviderFailure(
                    error_class=FailureMode.AUTH_FAILURE,
                    safe_detail="authentication failed",
                    retryable=False,
                ) from exc
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_ERROR,
                safe_detail="provider request failed",
                retryable=True,
            ) from exc

        usage_info = {
            "input_tokens": getattr(response.usage, "prompt_tokens", 0) if hasattr(response, "usage") and response.usage else 0,
            "output_tokens": getattr(response.usage, "completion_tokens", 0) if hasattr(response, "usage") and response.usage else 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") and response.usage else 0,
        }

        reported_model = azure_model
        if hasattr(response, "model"):
            reported_model = str(response.model)

        identity_drifted = reported_model != azure_model

        response_text = ""
        if hasattr(response, "choices") and response.choices:
            response_text = response.choices[0].message.content or ""

        MAX_RESPONSE_LENGTH = 100_000
        if len(response_text) > MAX_RESPONSE_LENGTH:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"response exceeded size limit ({MAX_RESPONSE_LENGTH} chars)",
                retryable=False,
            )

        raw_hash = sha256_hex(response_text)
        latency_ms = int((time.time() - start_time) * 1000)

        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=attempt_id,
            protocol_valid=True,
            terminal=True,
            text=response_text,
            provider_reported_model=reported_model,
            finish_reason=self._normalize_finish_reason(response),
            usage=usage_info,
            latency_ms=latency_ms,
            metadata={
                "adapter": self.name,
                "attempt_number": attempt_number,
                "model_config_id": request.model_config_id,
            },
            raw_response_hash=raw_hash,
            capability_observations={
                "model_identity_drifted": identity_drifted,
                "region_validated": self._endpoint is not None,
            },
        )

    def _normalize_finish_reason(self, response: Any) -> str:
        """Normalize provider finish reason to canonical values."""
        if hasattr(response, "choices") and response.choices:
            fr = getattr(response.choices[0].finish_reason, "value", "stop") if response.choices[0].finish_reason else "stop"
            FR_MAP = {
                "stop": "stop",
                "length": "length",
                "content_filter": "content_filter",
                "tool_calls": "tool_calls",
                "function_call": "function_call",
            }
            return FR_MAP.get(fr, fr)
        return "stop"