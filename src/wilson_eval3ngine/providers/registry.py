from __future__ import annotations

from .base import ProviderAdapter
from .mock import DeterministicMockProvider


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
                "the foundation build ships only the deterministic mock adapter"
            ) from exc
