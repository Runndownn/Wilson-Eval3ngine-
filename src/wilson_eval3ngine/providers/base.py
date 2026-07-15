from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..domain.contracts import ProviderRequest, ProviderResponse


@dataclass(slots=True)
class ProviderFailure(RuntimeError):
    error_class: str
    safe_detail: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.error_class}: {self.safe_detail}"


class ProviderAdapter(Protocol):
    name: str

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse: ...
