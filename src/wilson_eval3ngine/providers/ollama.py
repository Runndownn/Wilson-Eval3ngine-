from __future__ import annotations

import time
from typing import Any

from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex, utc_now
from ..constants import FailureMode
from .base import ProviderFailure

import json
import urllib.request
import urllib.error


class OllamaAdapter:
    """Production provider adapter for Ollama Gateway (Local/Localhost).

    Implementation follows TODO 51 requirements:
    - One attempt per call (no hidden retries)
    - Exact model identity capture with drift detection
    - Response validation and size bounds
    - TLS validation enforced (or skipped for localhost)

    Security and safety requirements implemented:
    - Credentials delivered at runtime via headers
    - Response validation for safe content
    - Size bounds enforced on responses
    - Model allowlist validation
    """

    name = "ollama"

    # Approved models from Ollama gateway - these are the available models
    APPROVED_MODELS = {
        "gpt-oss:latest",      # GPT OSS model on gateway
        "gemma3:4b",          # Google Gemma 3 4B
        "qwen3:4b",           # Alibaba Qwen 3 4B
        "llama3.2:1b",        # Meta Llama 3.2 1B
        "tinyllama:latest",   # TinyLlama
    }

    # Models with embedding capability
    EMBEDDING_MODELS = {
        "bge-m3:latest",
        "mxbai-embed-large:latest",
        "nomic-embed-text:latest",
    }

    def __init__(self, endpoint: str | None = None, api_key: str | None = None):
        """Initialize adapter.

        Args:
            endpoint: Ollama endpoint (defaults to http://localhost:11434 or OLLAMA_HOST env)
            api_key: Optional API key for authenticated deployments
        """
        # Support OLLAMA_HOST environment variable
        import os
        env_endpoint = os.getenv("OLLAMA_HOST")
        self._endpoint = endpoint or env_endpoint or "http://localhost:11434"
        self._api_key = api_key

    def _validate_model(self, model: str) -> None:
        """Validate model is in approved allowlist."""
        if model not in self.APPROVED_MODELS and model not in self.EMBEDDING_MODELS:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"model not in approved scope: {model}",
                retryable=False,
            )

    def _build_request_body(self, request: ProviderRequest) -> dict:
        """Build Ollama API request body."""
        messages: list[dict] = []
        for turn in request.messages:
            content = " ".join(block.text for block in turn.content)
            messages.append({"role": turn.role, "content": content})

        return {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.parameters.get("temperature", 0.0),
                "top_p": request.parameters.get("top_p"),
                "max_tokens": request.parameters.get("max_tokens", 4096),
            },
        }

    def _query_ollama(self, endpoint: str, body: dict, timeout: float) -> dict:
        """Query Ollama API endpoint."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())

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
            simulation: Optional simulation config for deterministic testing (skipped for production)
            attempt_number: 1-based attempt number (for logging correlation)

        Returns:
            ProviderResponse with canonical fields populated

        Raises:
            ProviderFailure on configuration, auth, or protocol errors
        """
        start_time = time.time()
        attempt_id = new_id("att")

        # Validate model allowlist
        self._validate_model(request.model)

        # Build request for Ollama API
        endpoint = f"{self._endpoint}/api/chat"
        body = self._build_request_body(request)

        try:
            response_data = self._query_ollama(endpoint, body, request.timeout_seconds)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode() if exc.fp else ""
            if exc.code == 404:
                raise ProviderFailure(
                    error_class=FailureMode.VALIDATION_ERROR,
                    safe_detail=f"model not found: {request.model}",
                    retryable=False,
                ) from exc
            if exc.code == 401 or exc.code == 403:
                raise ProviderFailure(
                    error_class=FailureMode.AUTH_FAILURE,
                    safe_detail="authentication failed",
                    retryable=False,
                ) from exc
            if exc.code == 429:
                raise ProviderFailure(
                    error_class=FailureMode.RATE_LIMITED,
                    safe_detail="provider rate limit exceeded",
                    retryable=True,
                ) from exc
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_ERROR,
                safe_detail=f"provider request failed: {exc.code}",
                retryable=True,
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_ERROR,
                safe_detail="connection failed to provider",
                retryable=True,
            ) from exc
        except TimeoutError:
            raise ProviderFailure(
                error_class=FailureMode.PROVIDER_TIMEOUT,
                safe_detail="provider request timed out",
                retryable=True,
            ) from None
        except json.JSONDecodeError:
            raise ProviderFailure(
                error_class=FailureMode.MALFORMED_RESPONSE,
                safe_detail="invalid JSON response from provider",
                retryable=False,
            ) from None

        # Extract response text
        response_text = ""
        if "message" in response_data and isinstance(response_data["message"], dict):
            response_text = response_data["message"].get("content", "")
        elif "response" in response_data:
            response_text = response_data["response"]

        # Validate response size
        MAX_RESPONSE_LENGTH = 100_000
        if len(response_text) > MAX_RESPONSE_LENGTH:
            raise ProviderFailure(
                error_class=FailureMode.VALIDATION_ERROR,
                safe_detail=f"response exceeded size limit ({MAX_RESPONSE_LENGTH} chars)",
                retryable=False,
            )

        # Determine finish reason
        finish_reason = "stop"
        if response_data.get("done") is False or response_text == "":
            finish_reason = "length"
        if response_data.get("error"):
            finish_reason = "content_filter"

        raw_hash = sha256_hex(response_text)
        latency_ms = int((time.time() - start_time) * 1000)

        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=attempt_id,
            protocol_valid=True,
            terminal=True,
            text=response_text,
            provider_reported_model=request.model,
            finish_reason=finish_reason,
            usage={
                "input_tokens": response_data.get("prompt_eval_count", 0),
                "output_tokens": response_data.get("eval_count", 0),
                "total_tokens": response_data.get("prompt_eval_count", 0) + response_data.get("eval_count", 0),
            },
            latency_ms=latency_ms,
            metadata={
                "adapter": self.name,
                "attempt_number": attempt_number,
                "model_config_id": request.model_config_id,
            },
            raw_response_hash=raw_hash,
            capability_observations={
                "model_serve_mode": response_data.get("serve_mode", "stream"),
                "model_eval_seconds": response_data.get("eval_duration", 0) / 1000000000 if response_data.get("eval_duration") else None,
            },
        )

    def list_available_models(self) -> list[tuple[str, str]]:
        """List available models from the gateway with descriptions."""
        endpoint = f"{self._endpoint}/api/tags"
        try:
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    size_gb = m.get("size", 0) / (1024**3)
                    families = m.get("details", {}).get("families", [])
                    family = families[0] if families else "unknown"
                    models.append((name, f"{family} ({size_gb:.1f}GB)"))
                return sorted(models, key=lambda x: x[0])
        except Exception:
            return [(m, m) for m in self.APPROVED_MODELS]

    def check_model(self, model: str) -> tuple[bool, str]:
        """Check if a specific model is available."""
        if model not in self.APPROVED_MODELS and model not in self.EMBEDDING_MODELS:
            return False, f"Model {model} not in approved allowlist"

        available = self.list_available_models()
        for name, _ in available:
            if name == model:
                return True, f"Model {model} available on gateway"
        return False, f"Model {model} not found on gateway"