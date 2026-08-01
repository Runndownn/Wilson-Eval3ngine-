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
                "available: mock (default), azure_openai, anthropic, ollama, claude_cli, kilo_cli, codex_cli"
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

    def register_claude_cli(self) -> None:
        """Register Claude CLI adapter for locally authenticated claude command."""
        from .cli_base import ClaudeCLIAdapter
        adapter = ClaudeCLIAdapter()
        if not adapter.detect_available():
            raise ValueError(
                "Claude CLI not available. Install from https://github.com/Kilo-Org/claw "
                "and ensure it's authenticated."
            )
        self.register("claude_cli", adapter)

    def register_kilo_cli(self) -> None:
        """Register Kilo CLI adapter for locally authenticated kilo command."""
        from .cli_base import KiloCLIAdapter
        adapter = KiloCLIAdapter()
        if not adapter.detect_available():
            raise ValueError(
                "Kilo CLI not available. Install and ensure it's authenticated."
            )
        self.register("kilo_cli", adapter)

    def register_codex_cli(self) -> None:
        """Register Codex CLI adapter for locally authenticated codex command."""
        from .cli_base import CodexCLIAdapter
        adapter = CodexCLIAdapter()
        if not adapter.detect_available():
            raise ValueError(
                "Codex CLI not available. Install from "
                "https://github.com/Kilo-Org/kilocode and ensure it's authenticated."
            )
        self.register("codex_cli", adapter)

    def available(self) -> list[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def auto_detect_cli_providers(self) -> list[str]:
        """Auto-detect available CLI providers and register them.

        Returns list of successfully registered CLI provider names.
        """
        registered = []
        for register_method in [
            self.register_claude_cli,
            self.register_kilo_cli,
            self.register_codex_cli,
        ]:
            try:
                register_method()
                registered.append(register_method.__name__.replace("register_", ""))
            except (ValueError, Exception):
                # Provider not available, skip silently
                pass
        return registered
