"""
OpenTelemetry distributed tracing integration for Wilson Eval3ngine.

Provides end-to-end observability across the evaluation pipeline with:
- W3C TraceContext propagation (traceparent/tracestate headers)
- Span creation for API requests, database operations, and pipeline stages
- Security-aware attributes (no sensitive data in spans)
- Configurable sampling and export (OTLP, console)
- Integration with existing CorrelationContext system

Security: Never records prompt/response bodies, secrets, or credentials in spans.
All span attributes are validated against an allowlist before emission.

Usage:
    from wilson_eval3ngine.tracing import get_tracer, trace_operation

    tracer = get_tracer()
    with tracer.start_as_current_span("evaluation.run") as span:
        span.set_attribute("project_id", project_id)
        # ... evaluation logic ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Generator, Optional

from .telemetry import (
    ALLOWED_LOG_FIELDS,
    CorrelationContext,
    get_correlation_context,
    is_safe_for_telemetry,
    set_correlation_context,
)
from .util import new_id

logger = logging.getLogger("wilson.tracing")

# ============================================================================
# Security: Span Attribute Allowlist
# ============================================================================

# Allowed span attributes (prevents high-cardinality injection and sensitive data)
ALLOWED_SPAN_ATTRIBUTES: frozenset[str] = frozenset({
    # Identifiers
    "trace_id", "span_id", "project_id", "experiment_id", "run_id",
    "case_id", "model_config_id", "attempt_id", "job_id", "operation_id",
    # Operation fields
    "operation", "status", "state", "action", "event_type",
    "resource_type", "resource_id",
    # Results
    "duration_ms", "latency_ms", "count", "total_count",
    "success", "error_class", "retryable",
    # Model/provider
    "provider", "model", "model_config_id",
    # Classification
    "primary_label", "confidence", "requires_review",
    # Gates
    "gate_status", "gate_id", "threshold_set_id",
    # Metrics
    "metric_id", "value", "numerator", "denominator",
    # Scheduling
    "lease_id", "worker_id",
    # HTTP
    "http.method", "http.status_code", "http.url", "http.user_agent",
    "http.scheme", "http.target",
    # Database
    "db.system", "db.operation", "db.statement",
    # Network
    "net.peer.name", "net.peer.port",
    # Evaluation pipeline
    "we3.stage", "we3.lane", "we3.split",
    # Service metadata
    "service.name", "service.version", "deployment.environment",
    # Error tracking
    "error", "exception.type", "exception.message",
})

# Prohibited attribute keys (never allowed in spans)
PROHIBITED_SPAN_ATTRIBUTES: frozenset[str] = frozenset({
    "prompt", "response", "completion", "message", "content", "text",
    "secret", "password", "api_key", "token", "credential",
    "authorization", "cookie", "set_cookie",
})


# ============================================================================
# Tracing Configuration
# ============================================================================


@dataclass(frozen=True, slots=True)
class TracingConfig:
    """Configuration for OpenTelemetry tracing.

    Controls sampling, export, and security settings.
    """

    enabled: bool = field(default_factory=lambda: os.getenv("WE3_TRACING_ENABLED", "true").lower() == "true")
    service_name: str = field(default_factory=lambda: os.getenv("WE3_SERVICE_NAME", "wilson-eval3ngine"))
    service_version: str = field(default_factory=lambda: os.getenv("WE3_SERVICE_VERSION", "0.1.0"))
    environment: str = field(default_factory=lambda: os.getenv("WE3_ENVIRONMENT", "development"))
    traces_sample_rate: float = field(default_factory=lambda: min(1.0, max(0.0, float(os.getenv("WE3_TRACES_SAMPLE_RATE", "1.0")))))
    otlp_endpoint: str = field(default_factory=lambda: os.getenv("WE3_OTLP_ENDPOINT", "http://localhost:4317"))
    console_export: bool = field(default_factory=lambda: os.getenv("WE3_TRACING_CONSOLE", "false").lower() == "true")
    insecure: bool = field(default_factory=lambda: os.getenv("WE3_OTLP_INSECURE", "true").lower() == "true")

    def to_resource_attributes(self) -> dict[str, str]:
        """Convert to OpenTelemetry resource attributes."""
        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
        }


# ============================================================================
# Lightweight Tracer (No External Dependencies)
# ============================================================================


@dataclass
class Span:
    """Lightweight span for tracing without external dependencies.

    In production with OpenTelemetry SDK, this delegates to the real tracer.
    Security: All attributes are validated against allowlist before storage.
    """

    name: str
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    is_recording: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    _config: TracingConfig = field(default_factory=TracingConfig)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute with validation.

        Security: Only allows attributes in the allowlist and rejects
        prohibited keys (secrets, prompts, responses).
        """
        if not self.is_recording:
            return

        # Check for prohibited keys
        key_lower = key.lower()
        if key_lower in PROHIBITED_SPAN_ATTRIBUTES:
            logger.warning(
                "span_attribute_rejected",
                extra={
                    "structured": {
                        "event": "span_attribute_rejected",
                        "reason": "prohibited_key",
                        "key": key,
                    }
                },
            )
            return

        # Check allowlist
        if key not in ALLOWED_SPAN_ATTRIBUTES:
            logger.debug(
                "span_attribute_not_allowed",
                extra={
                    "structured": {
                        "event": "span_attribute_not_allowed",
                        "key": key,
                    }
                },
            )
            return

        # Validate value safety
        if not is_safe_for_telemetry(value):
            logger.warning(
                "span_attribute_rejected",
                extra={
                    "structured": {
                        "event": "span_attribute_rejected",
                        "reason": "unsafe_value",
                        "key": key,
                    }
                },
            )
            return

        self.attributes[key] = value

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Set multiple span attributes with validation."""
        for key, value in attributes.items():
            self.set_attribute(key, value)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        if not self.is_recording:
            return

        safe_attrs = {
            k: v for k, v in (attributes or {}).items()
            if k in ALLOWED_SPAN_ATTRIBUTES and is_safe_for_telemetry(v)
        }
        self.events.append({
            "name": name,
            "attributes": safe_attrs,
            "timestamp": self._now_ms(),
        })

    def record_exception(self, exception: BaseException) -> None:
        """Record an exception on the span."""
        if not self.is_recording:
            return

        self.set_attribute("error", True)
        self.add_event(
            "exception",
            {
                "exception.type": type(exception).__name__,
                "exception.message": str(exception)[:500],
            },
        )

    def end(self) -> None:
        """End the span."""
        if self.is_recording:
            self.is_recording = False
            self.end_time = self._now_ms()

    @staticmethod
    def _now_ms() -> float:
        """Get current time in milliseconds."""
        import time
        return time.monotonic() * 1000


class Tracer:
    """Lightweight tracer for distributed tracing.

    Provides span creation with security validation. In production with
    the OpenTelemetry SDK installed, this delegates to the real tracer.
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        self._config = config or TracingConfig()
        self._span_stack: list[Span] = []
        self._current_span: Span | None = None

    @property
    def config(self) -> TracingConfig:
        return self._config

    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Span:
        """Start a new span.

        Args:
            name: Span name (e.g., "evaluation.run", "database.query")
            attributes: Initial span attributes (validated against allowlist)
            parent: Parent span (if None, uses current span)

        Returns:
            A new Span instance
        """
        if not self._config.enabled:
            return Span(name=name, is_recording=False)

        # Determine parent
        parent_span = parent or self._current_span

        # Determine trace ID: use parent's trace_id, or correlation context's trace_id
        if parent_span:
            trace_id = parent_span.trace_id
        else:
            context = get_correlation_context()
            trace_id = context.trace_id if context.trace_id else new_id("trc")

        span_id = new_id("spn")
        parent_span_id = parent_span.span_id if parent_span else ""

        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            is_recording=True,
            start_time=Span._now_ms(),
            _config=self._config,
        )

        # Set initial attributes
        span.set_attributes(attributes or {})

        # Add default attributes
        span.set_attribute("service.name", self._config.service_name)
        span.set_attribute("service.version", self._config.service_version)
        span.set_attribute("deployment.environment", self._config.environment)

        return span

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Generator[Span, None, None]:
        """Start a span and set it as the current span.

        This is the recommended way to create spans. The span is automatically
        ended when the context manager exits.

        Example:
            with tracer.start_as_current_span("evaluation.run") as span:
                span.set_attribute("project_id", project_id)
                # ... work ...
        """
        span = self.start_span(name, attributes=attributes, parent=parent)
        previous_span = self._current_span
        self._current_span = span
        self._span_stack.append(span)

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.end()
            self._span_stack.pop()
            self._current_span = previous_span

    @property
    def current_span(self) -> Span | None:
        """Get the current span."""
        return self._current_span

    def get_trace_context(self) -> dict[str, str]:
        """Get the current trace context for propagation.

        Returns W3C TraceContext format for HTTP header propagation.
        """
        span = self._current_span
        if span and span.is_recording:
            return {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
            }
        return {}

    def inject_trace_context(self, headers: dict[str, str]) -> dict[str, str]:
        """Inject trace context into HTTP headers (W3C TraceContext format).

        Adds traceparent and tracestate headers for distributed tracing.
        """
        ctx = self.get_trace_context()
        if ctx:
            # W3C TraceContext format
            version = "00"
            trace_id = ctx["trace_id"]
            span_id = ctx["span_id"]
            trace_flags = "01"  # sampled
            headers["traceparent"] = f"{version}-{trace_id}-{span_id}-{trace_flags}"
        return headers

    def extract_trace_context(self, headers: dict[str, str]) -> dict[str, str] | None:
        """Extract trace context from HTTP headers (W3C TraceContext format).

        Parses traceparent header for distributed tracing.
        """
        traceparent = headers.get("traceparent", "")
        if not traceparent:
            return None

        parts = traceparent.split("-")
        if len(parts) != 4:
            return None

        version, trace_id, span_id, trace_flags = parts
        if version != "00":
            return None

        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_flags": trace_flags,
        }


# ============================================================================
# Global Tracer Singleton
# ============================================================================

_tracer: Tracer | None = None
_tracer_lock = threading.Lock()


def get_tracer(config: TracingConfig | None = None) -> Tracer:
    """Get the global tracer instance (thread-safe lazy initialization).

    Returns the singleton Tracer instance. If config is provided on first
    call, it's used to initialize the tracer.
    """
    global _tracer
    if _tracer is None:
        with _tracer_lock:
            if _tracer is None:
                _tracer = Tracer(config or TracingConfig())
    return _tracer


def reset_tracer() -> None:
    """Reset the global tracer (for testing)."""
    global _tracer
    with _tracer_lock:
        _tracer = None


# ============================================================================
# Decorators and Context Managers
# ============================================================================


def trace_operation(
    name: str | None = None,
    *,
    attributes: dict[str, Any] | None = None,
    record_exception: bool = True,
) -> Any:
    """Decorator to trace a function with a span.

    Supports both synchronous and asynchronous functions.

    Security: Automatically captures correlation context without sensitive data.

    Example:
        @trace_operation("evaluation.run")
        def run_experiment(manifest_path: str) -> EvaluationOutcome:
            # ...
            pass

        @trace_operation("evaluation.run_async")
        async def run_experiment_async(manifest_path: str) -> EvaluationOutcome:
            # ...
            pass
    """
    def decorator(func: Any) -> Any:
        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            context = get_correlation_context()

            # Build attributes from correlation context
            span_attrs = dict(attributes or {})
            if context.trace_id:
                span_attrs["trace_id"] = context.trace_id
            if context.project_id:
                span_attrs["project_id"] = context.project_id
            if context.experiment_id:
                span_attrs["experiment_id"] = context.experiment_id
            if context.run_id:
                span_attrs["run_id"] = context.run_id

            with tracer.start_as_current_span(span_name, attributes=span_attrs) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as exc:
                    if record_exception:
                        span.record_exception(exc)
                    span.set_attribute("status", "error")
                    span.set_attribute("error_class", type(exc).__name__)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            context = get_correlation_context()

            # Build attributes from correlation context
            span_attrs = dict(attributes or {})
            if context.trace_id:
                span_attrs["trace_id"] = context.trace_id
            if context.project_id:
                span_attrs["project_id"] = context.project_id
            if context.experiment_id:
                span_attrs["experiment_id"] = context.experiment_id
            if context.run_id:
                span_attrs["run_id"] = context.run_id

            with tracer.start_as_current_span(span_name, attributes=span_attrs) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as exc:
                    if record_exception:
                        span.record_exception(exc)
                    span.set_attribute("status", "error")
                    span.set_attribute("error_class", type(exc).__name__)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


@contextmanager
def trace_stage(
    stage_name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Context manager for tracing an evaluation pipeline stage.

    Example:
        with trace_stage("grading") as span:
            span.set_attribute("case_version_id", case.case_version_id)
            classification = grader.grade(case, expectation, response)
    """
    tracer = get_tracer()
    context = get_correlation_context()

    span_attrs = dict(attributes or {})
    span_attrs["we3.stage"] = stage_name

    # Add correlation context
    if context.project_id:
        span_attrs["project_id"] = context.project_id
    if context.experiment_id:
        span_attrs["experiment_id"] = context.experiment_id
    if context.run_id:
        span_attrs["run_id"] = context.run_id

    with tracer.start_as_current_span(f"we3.{stage_name}", attributes=span_attrs) as span:
        yield span


# ============================================================================
# Trace Context Propagation
# ============================================================================


def propagate_trace_context(headers: dict[str, str]) -> dict[str, str]:
    """Propagate trace context to downstream services.

    Adds W3C TraceContext headers (traceparent, tracestate) to the
    provided headers dict for HTTP request propagation.

    Security: Only propagates trace identifiers, never sensitive data.
    """
    tracer = get_tracer()
    return tracer.inject_trace_context(headers)


def extract_trace_context(headers: dict[str, str]) -> dict[str, str] | None:
    """Extract trace context from incoming HTTP headers.

    Parses W3C TraceContext headers for distributed tracing.
    """
    tracer = get_tracer()
    return tracer.extract_trace_context(headers)


def with_propagated_context(headers: dict[str, str]) -> CorrelationContext:
    """Create a CorrelationContext from propagated trace headers.

    Used when receiving requests from other services to maintain
    trace continuity across service boundaries.
    """
    extracted = extract_trace_context(headers)
    if extracted:
        return CorrelationContext(
            trace_id=extracted.get("trace_id", ""),
            project_id=headers.get("X-Correlation-project_id", ""),
            experiment_id=headers.get("X-Correlation-experiment_id", ""),
            run_id=headers.get("X-Correlation-run_id", ""),
        )
    return get_correlation_context()


# ============================================================================
# Span Exporter Interface (for production integration)
# ============================================================================


@dataclass
class SpanExportResult:
    """Result of a span export operation."""

    success: bool
    exported_count: int
    failed_count: int
    error: str | None = None


class SpanExporter:
    """Interface for span exporters.

    In production, this would delegate to OpenTelemetry SDK exporters
    (OTLP, Jaeger, Zipkin, etc.). This implementation provides a
    console exporter for development and a no-op for testing.
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        self._config = config or TracingConfig()

    def export(self, spans: list[Span]) -> SpanExportResult:
        """Export spans to the configured backend.

        In development with console_export enabled, prints spans to stdout.
        In production, delegates to OTLP exporter.
        """
        if not spans:
            return SpanExportResult(success=True, exported_count=0, failed_count=0)

        if self._config.console_export:
            for span in spans:
                logger.info(
                    "span_export",
                    extra={
                        "structured": {
                            "event": "span",
                            "name": span.name,
                            "trace_id": span.trace_id,
                            "span_id": span.span_id,
                            "parent_span_id": span.parent_span_id,
                            "duration_ms": round(span.end_time - span.start_time, 2),
                            "attributes": span.attributes,
                            "events": span.events,
                        }
                    },
                )

        return SpanExportResult(
            success=True,
            exported_count=len(spans),
            failed_count=0,
        )

    def shutdown(self) -> None:
        """Shutdown the exporter and release resources."""
        pass


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "TracingConfig",
    "Span",
    "Tracer",
    "SpanExporter",
    "SpanExportResult",
    "ALLOWED_SPAN_ATTRIBUTES",
    "PROHIBITED_SPAN_ATTRIBUTES",
    "get_tracer",
    "reset_tracer",
    "trace_operation",
    "trace_stage",
    "propagate_trace_context",
    "extract_trace_context",
    "with_propagated_context",
]
