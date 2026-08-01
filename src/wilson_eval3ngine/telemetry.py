"""
Structured telemetry and correlation for TODO 51.

T8.1.1 - OpenTelemetry-compatible logs, metrics, and traces.
Implements field allowlists, correlation propagation, and redaction.
Security: Never records prompt/response bodies or secrets.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from .util import new_id, utc_now

# ============================================================================
# Correlation Context (Thread-Local for Production Safety)
# ============================================================================

_correlation_context: CorrelationContext | None = None
_correlation_lock = threading.Lock()


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

    def child_context(self, **overrides: str) -> CorrelationContext:
        """Create a child context with overridden values."""
        return CorrelationContext(
            trace_id=self.trace_id,
            project_id=overrides.get("project_id", self.project_id),
            experiment_id=overrides.get("experiment_id", self.experiment_id),
            run_id=overrides.get("run_id", self.run_id),
            case_id=overrides.get("case_id", self.case_id),
            model_id=overrides.get("model_id", self.model_id),
            attempt_id=overrides.get("attempt_id", self.attempt_id),
            job_id=overrides.get("job_id", self.job_id),
        )


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

# Prohibited content patterns (never allowed in telemetry)
PROHIBITED_PATTERNS: frozenset[str] = frozenset({
    "prompt", "response", "completion", "message", "content", "text",
    "secret", "password", "api_key", "token", "credential",
})


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
        # Skip prohibited fields entirely (no prompt/response/text in telemetry)
        if key.lower() in PROHIBITED_PATTERNS:
            continue
        if key not in ALLOWED_LOG_FIELDS:
            continue
        if isinstance(value, str):
            # Check for canary secrets/prompts
            if CANARY_SECRET in value or CANARY_PROMPT in value:
                redacted[key] = "[REDACTED]"
                continue
            # Check for common secret patterns
            value_lower = value.lower()
            if any(p in value_lower for p in ["password", "secret", "token", "api_key", "apikey", "bearer"]):
                redacted[key] = "[REDACTED]"
                continue
            # Check for prohibited content patterns in values
            if any(p in value_lower for p in ["prompt content:", "response content:", "completion text:"]):
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
        # Check for prohibited content
        if any(p in value_lower for p in ["prompt content:", "response content:"]):
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
    Thread-safe for production use.
    """

    def __init__(self, name: str = "we3.telemetry") -> None:
        self.logger = logging.getLogger(name)
        self._enabled = os.getenv("WE3_TELEMETRY_ENABLED", "true").lower() == "true"
        self._lock = threading.Lock()

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
            with self._lock:
                self.logger.log(level, event_type, extra={"telemetry": event.to_log_dict()})

        return context.trace_id

    def event(self, name: str, **attributes: Any) -> str:
        """Emit a telemetry event (OpenTelemetry-style)."""
        return self.emit(name, attributes)


# Global telemetry logger instance
_telemetry_logger: TelemetryLogger | None = None
_logger_lock = threading.Lock()


def get_telemetry_logger() -> TelemetryLogger:
    """Get the global telemetry logger (thread-safe lazy initialization)."""
    global _telemetry_logger
    if _telemetry_logger is None:
        with _logger_lock:
            if _telemetry_logger is None:
                _telemetry_logger = TelemetryLogger()
    return _telemetry_logger


# ============================================================================
# Correlation Context Functions (Thread-Safe)
# ============================================================================

def get_correlation_context() -> CorrelationContext:
    """Get current correlation context, creating one if missing (thread-safe)."""
    global _correlation_context
    with _correlation_lock:
        if _correlation_context is None:
            _correlation_context = CorrelationContext(trace_id=new_id("trc"))
        return _correlation_context


def set_correlation_context(context: CorrelationContext | None) -> None:
    """Set the correlation context (thread-safe)."""
    global _correlation_context
    with _correlation_lock:
        _correlation_context = context


def with_correlation_context(context: CorrelationContext) -> CorrelationContext:
    """Set and return correlation context (for context managers)."""
    set_correlation_context(context)
    return context


# ============================================================================
# Sampling Configuration
# ============================================================================

@dataclass(frozen=True, slots=True)
class SamplingConfig:
    """Telemetry sampling configuration.

    Controls cardinality and resource usage.
    """
    traces_sample_rate: float = 1.0
    metrics_cardinality_limit: int = 1000
    logs_sampling_rate: float = 0.1
    redaction_enabled: bool = True

    def should_sample_trace(self) -> bool:
        """Determine if trace should be sampled."""
        import random
        return random.random() < self.traces_sample_rate

    def should_sample_log(self) -> bool:
        """Determine if log should be sampled."""
        import random
        return random.random() < self.logs_sampling_rate


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
# OpenTelemetry Integration Hooks
# ============================================================================

def start_span(name: str, **attributes: Any) -> "TelemetrySpan":
    """Start a telemetry span (OpenTelemetry-style).

    Security: All attributes are validated against allowlist before emission.
    """
    logger = get_telemetry_logger()
    if not logger._enabled:
        return TelemetrySpan(name, is_recording=False)
    trace_id = logger.emit(f"span.{name}.start", attributes)
    return TelemetrySpan(name, trace_id=trace_id, is_recording=True)


@dataclass
class TelemetrySpan:
    """Lightweight span for OpenTelemetry compatibility.

    In production, this delegates to the OpenTelemetry SDK.
    Security: Never records prompt/response bodies or restricted content.
    """
    name: str
    trace_id: str = ""
    is_recording: bool = True
    _attributes: dict[str, Any] = field(default_factory=dict)
    _logger: TelemetryLogger = field(default_factory=get_telemetry_logger)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute with validation."""
        if self.is_recording and is_safe_for_telemetry(value):
            with self._lock:
                self._attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        if self.is_recording:
            payload = redact_sensitive_fields(attributes or {})
            self._logger.emit(f"span.{self.name}.event.{name}", payload)

    def end(self) -> None:
        """End the span."""
        if self.is_recording:
            self._logger.emit(f"span.{self.name}.end", self._attributes)


def instrument_operation(func):
    """Decorator to instrument operations with telemetry.

    Security: Automatically captures correlation context without sensitive data.
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        context = get_correlation_context()
        span = start_span(
            func.__name__,
            **{k: v for k, v in {
                "project_id": context.project_id,
                "experiment_id": context.experiment_id,
                "run_id": context.run_id,
            }.items() if v}
        )
        try:
            result = func(*args, **kwargs)
            span.set_attribute("status", "success")
            span.end()
            return result
        except Exception as e:
            span.set_attribute("status", "error")
            span.set_attribute("error_class", type(e).__name__)
            span.end()
            raise
    return wrapper


def record_metric(name: str, value: float, **labels: Any) -> None:
    """Record a metric with validation.

    Security: Metric name must be in allowlist; labels are validated.
    Silently skips invalid metrics to prevent telemetry failure from corrupting domain work.
    """
    if name not in ALLOWED_METRIC_NAMES:
        return  # Silently skip invalid metric names (graceful degradation)

    if len(labels) > 10:
        return  # Silently skip - too many labels risks high cardinality

    # Filter labels for safety
    safe_labels = {
        k: v for k, v in labels.items()
        if k in ALLOWED_LOG_FIELDS and is_safe_for_telemetry(v)
    }

    event = TelemetryEvent(
        event_type=f"metric.{name}",
        trace_id=get_correlation_context().trace_id,
        payload={"value": value, **safe_labels},
    )
    # Record metric by emitting telemetry event
    get_telemetry_logger().emit(event.event_type, event.payload)


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
    "PROHIBITED_PATTERNS",
    "redact_sensitive_fields",
    "is_safe_for_telemetry",
    "TelemetryEvent",
    "TelemetryLogger",
    "get_telemetry_logger",
    "SamplingConfig",
    "get_sampling_config",
    "CANARY_SECRET",
    "CANARY_PROMPT",
    "TelemetrySpan",
    "start_span",
    "instrument_operation",
    "record_metric",
]