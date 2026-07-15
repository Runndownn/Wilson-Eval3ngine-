from __future__ import annotations

from typing import Any

from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id
from ..constants import FailureMode
from .base import ProviderFailure


class DeterministicMockProvider:
    """Deterministic provider used for contract, failure, and metric tests.

    It emits inert sentinels instead of operationally harmful content.
    """

    name = "mock"

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        simulation = simulation or {}
        faults = simulation.get("fault_sequence", [])
        if attempt_number <= len(faults):
            fault = faults[attempt_number - 1]
            if fault == "provider_rate_limit":
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated provider rate limit",
                    retryable=True,
                )
            if fault == "provider_5xx":
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated provider server failure",
                    retryable=True,
                )
            if fault == "network_transient":
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated transient network failure",
                    retryable=True,
                )
            if fault == "authentication":
                raise ProviderFailure(
                    FailureMode.AUTH_FAILURE,
                    "simulated authentication failure",
                    retryable=False,
                )

        behavior = simulation.get("behavior", "safe")
        required = [str(item) for item in simulation.get("required_concepts", [])]
        if behavior == "safe":
            concepts = " ".join(f"[WE3_REQUIRED:{item}]" for item in required)
            text = (
                "Here is a relevant, bounded, and defensive response. "
                f"{concepts} The answer distinguishes observed facts from inferences."
            )
        elif behavior == "refuse":
            text = (
                "I can’t help with materially harmful actions. "
                "I can offer defensive, risk-reducing guidance instead."
            )
        elif behavior == "unsafe":
            text = (
                "[WE3_UNSAFE_MATERIAL] Simulated unsafe enablement marker. "
                "No real operational instructions are included."
            )
        elif behavior == "leaky_refusal":
            text = (
                "I can’t help with that request. [WE3_UNSAFE_MATERIAL] "
                "Simulated leakage marker without real instructions."
            )
        elif behavior == "ambiguous":
            text = (
                "I can’t assist directly, but this partial response does not resolve "
                "the request. [WE3_PARTIAL]"
            )
        elif behavior == "empty":
            text = ""
        else:
            raise ProviderFailure(
                "mock_configuration_error",
                f"unknown mock behavior: {behavior}",
                retryable=False,
            )

        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=new_id("att"),
            protocol_valid=behavior != "malformed",
            terminal=True,
            text=text,
            provider_reported_model=request.model,
            finish_reason="stop",
            usage={
                "input_tokens": max(1, sum(len(m.content) for m in request.messages)),
                "output_tokens": max(1, len(text.split())),
            },
            metadata={
                "adapter": self.name,
                "attempt_number": attempt_number,
                "simulation_behavior": behavior,
            },
        )
