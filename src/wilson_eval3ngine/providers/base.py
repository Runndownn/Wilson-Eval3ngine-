from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..domain.contracts import ProviderRequest, ProviderResponse


@dataclass(slots=True)
class ProviderFailure(RuntimeError):
    """Canonical provider failure exception.

    Extension rules:
        - error_class MUST be one of FailureMode constants
        - safe_detail MUST NOT include credentials, secrets, or PII
        - retryable indicates whether scheduler should retry
    """
    error_class: str
    safe_detail: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.error_class}: {self.safe_detail}"


@runtime_checkable
class ProviderAdapter(Protocol):
    """Canonical provider adapter protocol.

    All provider implementations MUST:
        1. Perform exactly one attempt per call
        2. Return ProviderResponse with canonical fields populated
        3. Keep credentials out of request/response objects
        4. Implement seed-based determinism for testing
        5. Use namespaced metadata under 'provider_metadata' key

    Metadata extension rules:
        Provider-specific fields in metadata MUST be nested under 'provider_metadata'
        to prevent namespace pollution. Core fields (text, usage, finish_reason)
        are canonical and cannot be overridden by extensions.
    """

    name: str

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        """Execute one provider attempt.

        Args:
            request: Canonical provider request with hashed payload
            simulation: Optional simulation config for deterministic testing
            attempt_number: 1-based attempt number (for retry tracking)

        Returns:
            ProviderResponse with canonical fields and optional extensions
        """
        ...
