from __future__ import annotations

from typing import Any

from .base import ProviderAdapter
from .mock import DeterministicMockProvider

# Lazy imports for optional providers to avoid import errors when dependencies missing
# These are only needed when the adapters are explicitly registered


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {
            "mock": DeterministicMockProvider(),
        }

    def register(self, name: str, adapter: ProviderAdapter) -> None:
        if name in self._providers:
            raise ValueError(f"provider already registered: {name}")
        self._providers[name] = adapter

    def get(self, name: str) -> ProviderAdapter:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(
                f"provider {name!r} is not registered; "
                "available: mock (default), azure_openai, anthropic, ollama"
            ) from exc

    def register_azure_openai(
        self, endpoint: str | None = None, credential: Any = None
    ) -> None:
        """Register Azure OpenAI adapter with optional explicit configuration."""
        from .azure_openai import AzureOpenAIAdapter
        self.register("azure_openai", AzureOpenAIAdapter(endpoint, credential))

    def register_anthropic(self, api_key: str | None = None) -> None:
        """Register Anthropic adapter with optional explicit configuration."""
        from .anthropic import AnthropicAdapter
        self.register("anthropic", AnthropicAdapter(api_key))

    def register_ollama(self, endpoint: str | None = None, api_key: str | None = None) -> None:
        """Register Ollama adapter with optional explicit configuration."""
        from .ollama import OllamaAdapter
        self.register("ollama", OllamaAdapter(endpoint, api_key))

    def available(self) -> list[str]:
        """List registered provider names."""
        return list(self._providers.keys())
