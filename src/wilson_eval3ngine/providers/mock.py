from __future__ import annotations

from random import Random
from typing import Any

from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex
from ..constants import FailureMode
from .base import ProviderFailure


class DeterministicMockProvider:
    """Deterministic provider used for contract, failure, and metric tests.

    It emits inert sentinels instead of operationally harmful content.
    Uses seeded randomness for reproducible fault scenarios.

    Extension rules:
        Provider-specific metadata MUST be namespaced under 'provider_metadata' key.
        Core fields (text, usage, finish_reason) are canonical and cannot be overridden.
    """

    name = "mock"

    # Supported capabilities for observation mode
    SUPPORTED_CAPABILITIES = [
        "streaming",
        "function_calling",
        "json_mode",
        "system_messages",
    ]

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        simulation = simulation or {}
        seed: int = simulation.get("seed", 0)
        rng = Random(seed + attempt_number)

        # Build provider metadata extension (namespaced)
        provider_metadata: dict[str, Any] = {}

        faults = simulation.get("fault_sequence", [])
        if attempt_number <= len(faults):
            fault = faults[attempt_number - 1]
            if fault == "provider_timeout":
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated provider timeout",
                    retryable=True,
                )
            if fault == "provider_rate_limit":
                provider_metadata["mock_rate_limit_remaining"] = 0
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated provider rate limit",
                    retryable=True,
                )
            if fault == "provider_5xx":
                raise ProviderFailure(
                    FailureMode.PROVIDER_TIMEOUT,
                    "simulated provider server failure (5xx)",
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
            if fault == "malformed_response":
                # Return response with malformed content
                return ProviderResponse(
                    run_id=request.run_id,
                    attempt_id=new_id("att"),
                    protocol_valid=False,
                    terminal=False,
                    text="[WE3_MALFORMED] Simulated malformed response - invalid JSON structure",
                    provider_reported_model=request.model,
                    finish_reason="malformed",
                    usage={"malformed": True},
                    latency_ms=rng.randint(50, 150),
                    metadata={
                        "adapter": self.name,
                        "attempt_number": attempt_number,
                        "simulation_fault": fault,
                    },
                    raw_response_hash=sha256_hex(f"malformed_response_attempt_{attempt_number}"),
                )
            if fault == "partial_stream":
                # Simulate streaming disconnect with partial content
                partial_text = "This is a partial response that was cut off due to streaming disconnect."
                return ProviderResponse(
                    run_id=request.run_id,
                    attempt_id=new_id("att"),
                    protocol_valid=True,
                    terminal=False,
                    text=partial_text,
                    provider_reported_model=request.model,
                    finish_reason="stream_error",
                    usage={"input_tokens": 10, "output_tokens": len(partial_text.split())},
                    latency_ms=rng.randint(100, 300),
                    metadata={
                        "adapter": self.name,
                        "attempt_number": attempt_number,
                        "simulation_fault": fault,
                    },
                    raw_response_hash=sha256_hex(partial_text),
                )
            if fault == "usage_anomaly":
                # Return response with suspicious usage metadata
                return ProviderResponse(
                    run_id=request.run_id,
                    attempt_id=new_id("att"),
                    protocol_valid=True,
                    terminal=True,
                    text="Response with anomalous usage reporting.",
                    provider_reported_model=request.model,
                    finish_reason="stop",
                    usage={"input_tokens": -100, "output_tokens": 999999},
                    latency_ms=rng.randint(50, 150),
                    metadata={
                        "adapter": self.name,
                        "attempt_number": attempt_number,
                        "simulation_fault": fault,
                    },
                    raw_response_hash=sha256_hex("usage_anomaly_response"),
                )
            if fault == "content_filter":
                # Simulate content filtering trigger
                return ProviderResponse(
                    run_id=request.run_id,
                    attempt_id=new_id("att"),
                    protocol_valid=True,
                    terminal=True,
                    text="",
                    provider_reported_model=request.model,
                    finish_reason="content_filter",
                    usage={"input_tokens": 10, "output_tokens": 0},
                    latency_ms=rng.randint(200, 400),
                    metadata={
                        "adapter": self.name,
                        "attempt_number": attempt_number,
                        "simulation_fault": fault,
                    },
                    raw_response_hash=sha256_hex(""),
                )
            if fault == "model_identity_drift":
                # Simulate provider returning different model than requested
                return ProviderResponse(
                    run_id=request.run_id,
                    attempt_id=new_id("att"),
                    protocol_valid=True,
                    terminal=True,
                    text="Response from unexpected model version.",
                    provider_reported_model=f"drifted-model-{attempt_number}",
                    finish_reason="stop",
                    usage={"input_tokens": 10, "output_tokens": 5},
                    latency_ms=rng.randint(50, 150),
                    metadata={
                        "adapter": self.name,
                        "attempt_number": attempt_number,
                        "simulation_fault": fault,
                    },
                    raw_response_hash=sha256_hex("identity_drift_response"),
                )

        # Check for usage anomaly parameter
        usage_anomaly = simulation.get("usage_anomaly")
        if usage_anomaly:
            provider_metadata["usage_anomaly"] = usage_anomaly

        behavior = simulation.get("behavior", "safe")
        required = [str(item) for item in simulation.get("required_concepts", [])]

        # Determine capability observations
        capability_observations = {}
        if simulation.get("observe_capabilities", False):
            capability_observations = {
                "streaming_supported": rng.random() > 0.3,
                "function_calling_supported": True,
                "json_mode_supported": True,
            }

        # Simulate latency (deterministic based on seed)
        base_latency = simulation.get("latency_ms", 100)
        latency = base_latency + (rng.randint(-20, 50) if seed else 0)

        if behavior == "safe":
            concepts = " ".join(f"[WE3_REQUIRED:{item}]" for item in required)
            text = (
                "Here is a relevant, bounded, and defensive response. "
                f"{concepts} The answer distinguishes observed facts from inferences."
            )
        elif behavior == "refuse":
            text = (
                "I can't help with materially harmful actions. "
                "I can offer defensive, risk-reducing guidance instead."
            )
        elif behavior == "unsafe":
            text = (
                "[WE3_UNSAFE_MATERIAL] Simulated unsafe enablement marker. "
                "No real operational instructions are included."
            )
        elif behavior == "leaky_refusal":
            text = (
                "I can't help with that request. [WE3_UNSAFE_MATERIAL] "
                "Simulated leakage marker without real instructions."
            )
        elif behavior == "ambiguous":
            text = (
                "I can't assist directly, but this partial response does not resolve "
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

        # Compute raw response hash
        raw_response_payload = f"{text}:{behavior}:{attempt_number}"
        raw_hash = sha256_hex(raw_response_payload)

        # Build usage from message content with optional anomaly injection
        input_tokens = max(1, sum(len(m.content) for m in request.messages))
        output_tokens = max(1, len(text.split()))

        if usage_anomaly == "inflated":
            output_tokens = int(output_tokens * 100)
        elif usage_anomaly == "missing":
            input_tokens = output_tokens = 0

        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=new_id("att"),
            protocol_valid=behavior != "malformed",
            terminal=True,
            text=text,
            provider_reported_model=request.model,
            finish_reason="stop",
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            latency_ms=latency,
            raw_response_hash=raw_hash,
            capability_observations=capability_observations,
            metadata={
                "adapter": self.name,
                "attempt_number": attempt_number,
                "simulation_behavior": behavior,
                "provider_metadata": provider_metadata,
            },
        )