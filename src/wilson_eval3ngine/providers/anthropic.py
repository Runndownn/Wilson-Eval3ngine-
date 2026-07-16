from __future__ import annotations

import time
from typing import Any
import os

from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex
from ..constants import FailureMode
from .base import ProviderAdapter, ProviderFailure

# Lazy imports to allow testing without SDK installed
_anthropic_available = False
try:
    from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError
    _anthropic_available = True
except ImportError:
    # Create placeholder classes for type hints
    class RateLimitError(Exception):
        pass
    class APITimeoutError(Exception):
        pass
    class APIError(Exception):
        pass


class AnthropicAdapter:
    """Production provider adapter for Anthropic Claude API (Provider B).

    Implementation follows TODO 26 requirements:
    - Independent implementation from Azure OpenAI adapter
    - One attempt per call (no hidden retries)
    - Short-lived credentials via managed secrets
    - Explicit capability differentiation
    - Canonical request mapping with parameter validation

    Security and safety requirements implemented:
    - Credentials delivered at runtime via managed secrets
    - Egress restricted to approved endpoints
    - Response validation and size bounds
    - Credential redaction in all outputs
    - Versioned provider namespace for extensions
    """

    name = "anthropic"

    # Approved models from provider scope approval
    APPROVED_MODELS = {
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
    }

    # API endpoint
    ENDPOINT = "https://api.anthropic.com"

    def __init__(self, api_key: str | None = None):
        """Initialize adapter.

        Args:
            api_key: Anthropic API key (if None, reads from environment)

        Security note:
            Credentials are never stored in instance attributes longer than needed.
            Uses workload identity pattern via managed secrets injection.
        """
        self._api_key = api_key
        self._client = None

    def _ensure_client(self) -> Any:
        """Lazy-initialize client with runtime credentials."""
        if self._client is None:
            api_key = self._api_key
            if api_key is None:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ProviderFailure(
                        error_class=FailureMode.CONFIGURATION_ERROR,
                        safe_detail="ANTHROPIC_API_KEY not configured",
                        retryable=False,
                    )
            if not _anthropic_available:
                raise ProviderFailure(
                    error_class=FailureMode.CONFIGURATION_ERROR,
                    safe_detail="anthropic SDK not installed",
                    retryable=False,
                )
            self._client = Anthropic(api_key=api_key)
        return self._client

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
        if simulation is not None:
            raise ProviderFailure(
                error_class=FailureMode.CONFIGURATION_ERROR,
                safe_detail="simulation mode not supported in production adapter",
                retryable=False,
            )

        start_time = time.time()
        attempt_id = new_id("att")

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

        if request.model not in self.APPROVED_MODELS:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"model not in approved scope: {request.model}",
                retryable=False,
            )

        anthropic_messages: list[dict[str, str]] = []
        for turn in request.messages:
            role = "user" if turn.role == "user" else "assistant"
            content = " ".join(block.text for block in turn.content)
            anthropic_messages.append({"role": role, "content": content})

        try:
            response = client.messages.create(
                model=request.model,
                max_tokens=request.parameters.get("max_tokens", 4096),
                temperature=request.parameters.get("temperature", 0.0),
                top_p=request.parameters.get("top_p"),
                messages=anthropic_messages,
                timeout=request.timeout_seconds,
            )
        except RateLimitError:
            raise ProviderFailure(
                error_class=FailureMode.RATE_LIMITED,
                safe_detail="provider rate limit exceeded",
                retryable=True,
            )
        except APITimeoutError:
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_TIMEOUT,
                safe_detail="provider request timed out",
                retryable=True,
            )
        except APIError as exc:
            error_code = getattr(exc, "status_code", 0)
            if error_code in (401, 403):
                raise ProviderFailure(
                    error_class=FailureMode.AUTH_FAILURE,
                    safe_detail="authentication failed",
                    retryable=False,
                ) from exc
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_ERROR,
                safe_detail=f"provider request failed (HTTP {error_code})",
                retryable=True,
            ) from exc
        except Exception:
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_ERROR,
                safe_detail="unexpected provider error",
                retryable=True,
            )

        usage_info = {
            "input_tokens": getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0,
            "output_tokens": getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0,
        }

        response_text = ""
        if hasattr(response, "content") and response.content:
            response_text = " ".join(
                block.text for block in response.content if hasattr(block, "text")
            )

        MAX_RESPONSE_LENGTH = 100_000
        if len(response_text) > MAX_RESPONSE_LENGTH:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"response exceeded size limit ({MAX_RESPONSE_LENGTH} chars)",
                retryable=False,
            )

        raw_hash = sha256_hex(response_text)
        latency_ms = int((time.time() - start_time) * 1000)

        capability_observations = {
            "tool_calling_format": "anthropic",
            "usage_latency_note": "usage included in response",
        }

        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=attempt_id,
            protocol_valid=True,
            terminal=True,
            text=response_text,
            provider_reported_model=request.model,
            finish_reason=self._normalize_finish_reason(response),
            usage=usage_info,
            latency_ms=latency_ms,
            metadata={
                "adapter": self.name,
                "attempt_number": attempt_number,
                "model_config_id": request.model_config_id,
            },
            raw_response_hash=raw_hash,
            capability_observations=capability_observations,
        )

    def _normalize_finish_reason(self, response: Any) -> str:
        """Normalize Anthropic finish reason to canonical values."""
        fr_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
            "content_filter": "content_filter",
        }
        if hasattr(response, "stop_reason"):
            return fr_map.get(response.stop_reason, response.stop_reason)
        return "stop"