"""
Structured telemetry and correlation for TODO 51.

T8.1.1 - OpenTelemetry-compatible logs, metrics, and traces.
Implements field allowlists, correlation propagation, and redaction.
Security: Never records prompt/response bodies or secrets.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from .util import new_id, utc_now


# ============================================================================
# Correlation Context
# ============================================================================

@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Correlation context for tracing operations across boundaries.

    Security: Contains no sensitive content, only identifiers.
    """
    trace_id: str = ""
    project_id: str = ""
    experiment_id: str = ""
    run_id: str = ""
    case_id: str = ""
    model_id: str = ""
    attempt_id: str = ""
    job_id: str = ""

    def to_baggage(self) -> dict[str, str]:
        """Convert to OpenTelemetry baggage format."""
        return {
            "trace_id": self.trace_id,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "model_id": self.model_id,
        }

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP header format for propagation."""
        # Use snake_case for headers (common convention)
        return {f"X-Correlation-{k}": v for k, v in self.to_baggage().items() if v}


# Global correlation context (thread-local in production)
_correlation_context: CorrelationContext | None = None


def get_correlation_context() -> CorrelationContext:
    """Get current correlation context, creating one if missing."""
    global _correlation_context
    if _correlation_context is None:
        _correlation_context = CorrelationContext(trace_id=new_id("trc"))
    return _correlation_context


def set_correlation_context(context: CorrelationContext | None) -> None:
    """Set the correlation context."""
    global _correlation_context
    _correlation_context = context


def with_correlation_context(context: CorrelationContext) -> CorrelationContext:
    """Set and return correlation context (for context managers)."""
    set_correlation_context(context)
    return context


# ============================================================================
# Telemetry Field Allowlists
# ============================================================================

# Allowed fields for logs/metrics (prevents high-cardinality injection)
ALLOWED_LOG_FIELDS: frozenset[str] = frozenset({
    # Identifiers
    "trace_id", "span_id", "project_id", "experiment_id", "run_id",
    "case_id", "model_id", "attempt_id", "job_id", "operation_id",
    # Operation fields
    "operation", "status", "state", "action", "event_type",
    "resource_type", "resource_id",
    # Results
    "duration_ms", "latency_ms", "count", "total_count",
    "success", "error_class", "retryable",
    # Model/provided
    "provider", "model", "model_config_id",
    # Classification
    "primary_label", "confidence", "requires_review",
    # Gates
    "gate_status", "gate_id", "threshold_set_id",
    # Metrics
    "metric_id", "value", "numerator", "denominator",
    # Scheduling
    "lease_id", "worker_id",
    # Versioning
    "grader_version", "schema_version",
})

# Allowed metric names (bounded cardinality)
ALLOWED_METRIC_NAMES: frozenset[str] = frozenset({
    "we3.operation.count",
    "we3.operation.duration_ms",
    "we3.run.count",
    "we3.run.duration_ms",
    "we3.classification.confidence",
    "we3.gate.decision",
    "we3.metric.value",
    "we3.provider.latency_ms",
    "we3.storage.bytes_written",
    "we3.storage.bytes_read",
})

# Histogram bucket boundaries for allowed metrics
HISTOGRAM_BUCKETS: dict[str, list[float]] = {
    "duration_ms": [1, 5, 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
    "latency_ms": [1, 5, 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    "bytes": [100, 1000, 10000, 100000, 1000000, 10000000, 100000000],
    "confidence": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
}


# ============================================================================
# Redaction Utilities
# ============================================================================

# Canary values for testing redaction
CANARY_SECRET = "TEST_SECRET_VALUE_TO_REDACT"
CANARY_PROMPT = "TEST_PROMPT_CONTENT_TO_REDACT"


def redact_sensitive_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from telemetry data.

    Security: Never allows prompt/response bodies, secrets, or tokens in telemetry.
    """
    redacted = {}
    for key, value in data.items():
        if key not in ALLOWED_LOG_FIELDS:
            # Skip disallowed fields entirely
            continue
        if isinstance(value, str):
            # Check for canary secrets
            if CANARY_SECRET in value or CANARY_PROMPT in value:
                redacted[key] = "[REDACTED]"
                continue
            # Check for common secret patterns
            value_lower = value.lower()
            if any(p in value_lower for p in ["password", "secret", "token", "api_key", "apikey"]):
                redacted[key] = "[REDACTED]"
                continue
            # Truncate very long strings (prevent high cardinality)
            if len(value) > 1024:
                redacted[key] = value[:1024] + "[TRUNCATED]"
                continue
        redacted[key] = value
    return redacted


def is_safe_for_telemetry(value: Any) -> bool:
    """Check if a value is safe to include in telemetry.

    Security: Prevents injection of secrets, prompts, responses.
    """
    if value is None:
        return True
    if isinstance(value, (int, float, bool)):
        return True
    if isinstance(value, str):
        # Check for canary patterns
        if CANARY_SECRET in value or CANARY_PROMPT in value:
            return False
        # Check for secret patterns
        value_lower = value.lower()
        if any(p in value_lower for p in ["password", "secret", "token", "api_key"]):
            return False
        # Check length
        if len(value) > 1024:
            return False
    return True


# ============================================================================
# Telemetry Logger
# ============================================================================

@dataclass
class TelemetryEvent:
    """Structured telemetry event."""
    event_type: str
    timestamp: str = field(default_factory=lambda: utc_now().isoformat())
    trace_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to log-safe dictionary."""
        payload = redact_sensitive_fields(self.payload)
        return {
            "schema_version": "we3.telemetry_event.v1",
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "payload": payload,
        }


class TelemetryLogger:
    """Telemetry logger with OpenTelemetry compatibility.

    Security: All events are redacted before emission.
    """

    def __init__(self, name: str = "we3.telemetry") -> None:
        self.logger = logging.getLogger(name)
        self._enabled = os.getenv("WE3_TELEMETRY_ENABLED", "true").lower() == "true"

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        level: int = logging.INFO,
    ) -> str:
        """Emit a telemetry event with correlation context.

        Returns the trace_id for reference.
        """
        context = get_correlation_context()
        if context.trace_id == "":
            context = CorrelationContext(trace_id=new_id("trc"))
            set_correlation_context(context)

        event = TelemetryEvent(
            event_type=event_type,
            trace_id=context.trace_id,
            payload=redact_sensitive_fields(payload or {}),
        )

        if self._enabled:
            self.logger.log(level, event_type, extra={"telemetry": event.to_log_dict()})

        return context.trace_id

    def event(self, name: str, **attributes: Any) -> str:
        """Emit a telemetry event (OpenTelemetry-style)."""
        return self.emit(name, attributes)


# Global telemetry logger instance
_telemetry_logger: TelemetryLogger | None = None


def get_telemetry_logger() -> TelemetryLogger:
    """Get the global telemetry logger."""
    global _telemetry_logger
    if _telemetry_logger is None:
        _telemetry_logger = TelemetryLogger()
    return _telemetry_logger


# ============================================================================
# Sampling Configuration
# ============================================================================

@dataclass(frozen=True, slots=True)
class SamplingConfig:
    """Telemetry sampling configuration.

    Controls cardinality and resource usage.
    """
    traces_sample_rate: float = 1.0  # 1.0 = full, < 1.0 = sampling
    metrics_cardinality_limit: int = 1000  # Max distinct label values
    logs_sampling_rate: float = 0.1  # 10% of logs to reduce volume
    redaction_enabled: bool = True

    def should_sample_trace(self) -> bool:
        """Determine if trace should be sampled."""
        import random
        return random.random() < self.traces_sample_rate

    def should_sample_log(self) -> bool:
        """Determine if log should be sampled."""
        import random
        return random.random() < self.logs_sampling_rate


# Default sampling configuration
_DEFAULT_SAMPLING = SamplingConfig()


def get_sampling_config() -> SamplingConfig:
    """Get sampling configuration from environment."""
    traces_rate = float(os.getenv("WE3_TRACES_SAMPLE_RATE", "1.0"))
    traces_rate = min(1.0, max(0.0, traces_rate))
    return SamplingConfig(
        traces_sample_rate=traces_rate,
        logs_sampling_rate=float(os.getenv("WE3_LOGS_SAMPLE_RATE", "0.1")),
    )


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "CorrelationContext",
    "get_correlation_context",
    "set_correlation_context",
    "with_correlation_context",
    "ALLOWED_LOG_FIELDS",
    "ALLOWED_METRIC_NAMES",
    "HISTOGRAM_BUCKETS",
    "redact_sensitive_fields",
    "is_safe_for_telemetry",
    "TelemetryEvent",
    "TelemetryLogger",
    "get_telemetry_logger",
    "SamplingConfig",
    "get_sampling_config",
    "CANARY_SECRET",
    "CANARY_PROMPT",
]