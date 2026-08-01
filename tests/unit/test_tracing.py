"""
Unit tests for the OpenTelemetry distributed tracing module.

Tests cover:
- Span creation and attribute validation (security allowlist)
- Tracer context management (start_as_current_span)
- W3C TraceContext propagation (inject/extract)
- Decorators (trace_operation)
- Context managers (trace_stage)
- CorrelationContext integration
- Prohibited attribute rejection
- Sampling and configuration
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from wilson_eval3ngine.tracing import (
    ALLOWED_SPAN_ATTRIBUTES,
    PROHIBITED_SPAN_ATTRIBUTES,
    Span,
    SpanExporter,
    SpanExportResult,
    Tracer,
    TracingConfig,
    extract_trace_context,
    get_tracer,
    propagate_trace_context,
    reset_tracer,
    trace_operation,
    trace_stage,
    with_propagated_context,
)
from wilson_eval3ngine.telemetry import CorrelationContext, set_correlation_context


# ============================================================================
# TracingConfig Tests
# ============================================================================


def test_tracing_config_defaults():
    """TracingConfig should have sensible defaults."""
    config = TracingConfig()
    assert config.service_name == "wilson-eval3ngine"
    assert config.service_version == "0.1.0"
    assert config.environment == "development"
    assert 0.0 <= config.traces_sample_rate <= 1.0


def test_tracing_config_from_env():
    """TracingConfig should read from environment variables."""
    with patch.dict(os.environ, {
        "WE3_TRACING_ENABLED": "false",
        "WE3_SERVICE_NAME": "test-service",
        "WE3_SERVICE_VERSION": "2.0.0",
        "WE3_ENVIRONMENT": "production",
        "WE3_TRACES_SAMPLE_RATE": "0.5",
        "WE3_OTLP_ENDPOINT": "http://collector:4317",
    }):
        config = TracingConfig()
        assert config.enabled is False
        assert config.service_name == "test-service"
        assert config.service_version == "2.0.0"
        assert config.environment == "production"
        assert config.traces_sample_rate == 0.5
        assert config.otlp_endpoint == "http://collector:4317"


def test_tracing_config_resource_attributes():
    """TracingConfig should produce correct resource attributes."""
    config = TracingConfig()
    attrs = config.to_resource_attributes()
    assert attrs["service.name"] == "wilson-eval3ngine"
    assert attrs["service.version"] == "0.1.0"
    assert attrs["deployment.environment"] == "development"


# ============================================================================
# Span Tests
# ============================================================================


def test_span_creation():
    """Span should be created with correct defaults."""
    span = Span(name="test.span")
    assert span.name == "test.span"
    assert span.is_recording is True
    assert span.attributes == {}
    assert span.events == []
    assert span.trace_id == ""
    assert span.span_id == ""


def test_span_set_attribute_allowed():
    """Span should accept attributes in the allowlist."""
    span = Span(name="test.span")
    span.set_attribute("project_id", "proj1")
    span.set_attribute("status", "success")
    span.set_attribute("duration_ms", 123.45)
    assert span.attributes["project_id"] == "proj1"
    assert span.attributes["status"] == "success"
    assert span.attributes["duration_ms"] == 123.45


def test_span_set_attribute_prohibited():
    """Span should reject prohibited attribute keys."""
    span = Span(name="test.span")
    span.set_attribute("password", "secret123")
    span.set_attribute("api_key", "key123")
    span.set_attribute("authorization", "Bearer token")
    assert "password" not in span.attributes
    assert "api_key" not in span.attributes
    assert "authorization" not in span.attributes


def test_span_set_attribute_not_in_allowlist():
    """Span should reject attributes not in the allowlist."""
    span = Span(name="test.span")
    span.set_attribute("custom_field", "value")
    assert "custom_field" not in span.attributes


def test_span_set_attributes():
    """Span should set multiple attributes at once."""
    span = Span(name="test.span")
    span.set_attributes({
        "project_id": "proj1",
        "status": "success",
        "custom_field": "should_be_rejected",
    })
    assert span.attributes["project_id"] == "proj1"
    assert span.attributes["status"] == "success"
    assert "custom_field" not in span.attributes


def test_span_add_event():
    """Span should add events with validated attributes."""
    span = Span(name="test.span")
    span.add_event("checkpoint", {"project_id": "proj1", "custom": "rejected"})
    assert len(span.events) == 1
    assert span.events[0]["name"] == "checkpoint"
    assert span.events[0]["attributes"]["project_id"] == "proj1"
    assert "custom" not in span.events[0]["attributes"]


def test_span_record_exception():
    """Span should record exceptions."""
    span = Span(name="test.span")
    try:
        raise ValueError("test error")
    except ValueError as exc:
        span.record_exception(exc)
    assert span.attributes.get("error") is True
    assert len(span.events) == 1
    assert span.events[0]["name"] == "exception"


def test_span_end():
    """Span should end and set end_time."""
    span = Span(name="test.span")
    assert span.is_recording is True
    span.end()
    assert span.is_recording is False
    assert span.end_time > 0


def test_span_not_recording_after_end():
    """Span should not accept attributes after ending."""
    span = Span(name="test.span")
    span.end()
    span.set_attribute("project_id", "proj1")
    assert span.attributes == {}


# ============================================================================
# Tracer Tests
# ============================================================================


def test_tracer_start_span():
    """Tracer should create spans with correct attributes."""
    tracer = Tracer()
    span = tracer.start_span("test.operation", attributes={"project_id": "proj1"})
    assert span.name == "test.operation"
    assert span.is_recording is True
    assert span.trace_id != ""
    assert span.span_id != ""
    assert span.attributes["project_id"] == "proj1"
    assert span.attributes["service.name"] == "wilson-eval3ngine"


def test_tracer_start_as_current_span():
    """Tracer should set span as current within context manager."""
    tracer = Tracer()
    with tracer.start_as_current_span("test.operation") as span:
        assert tracer.current_span is span
        assert span.is_recording is True
    assert tracer.current_span is None


def test_tracer_span_hierarchy():
    """Tracer should maintain parent-child span relationships."""
    tracer = Tracer()
    with tracer.start_as_current_span("parent") as parent:
        parent_span_id = parent.span_id
        with tracer.start_as_current_span("child") as child:
            assert child.parent_span_id == parent_span_id
            assert child.trace_id == parent.trace_id
            assert tracer.current_span is child
        assert tracer.current_span is parent


def test_tracer_exception_in_span():
    """Tracer should record exceptions in spans."""
    tracer = Tracer()
    with pytest.raises(ValueError):
        with tracer.start_as_current_span("failing.operation") as span:
            raise ValueError("test error")
    assert span.attributes.get("error") is True


def test_tracer_disabled():
    """Tracer should not record when disabled."""
    config = TracingConfig(enabled=False)
    tracer = Tracer(config)
    span = tracer.start_span("test.operation")
    assert span.is_recording is False


def test_tracer_get_trace_context():
    """Tracer should return trace context for propagation."""
    tracer = Tracer()
    with tracer.start_as_current_span("test.operation") as span:
        ctx = tracer.get_trace_context()
        assert ctx["trace_id"] == span.trace_id
        assert ctx["span_id"] == span.span_id


def test_tracer_inject_trace_context():
    """Tracer should inject trace context into HTTP headers."""
    tracer = Tracer()
    with tracer.start_as_current_span("test.operation"):
        headers = {}
        result = tracer.inject_trace_context(headers)
        assert "traceparent" in result
        assert result["traceparent"].startswith("00-")


def test_tracer_extract_trace_context():
    """Tracer should extract trace context from HTTP headers."""
    tracer = Tracer()
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    span_id = "b7ad6b7169203331"
    headers = {
        "traceparent": f"00-{trace_id}-{span_id}-01",
    }
    result = tracer.extract_trace_context(headers)
    assert result is not None
    assert result["trace_id"] == trace_id
    assert result["span_id"] == span_id
    assert result["trace_flags"] == "01"


def test_tracer_extract_invalid_trace_context():
    """Tracer should return None for invalid trace context."""
    tracer = Tracer()
    assert tracer.extract_trace_context({}) is None
    assert tracer.extract_trace_context({"traceparent": "invalid"}) is None
    assert tracer.extract_trace_context({"traceparent": "01-invalid-span-01"}) is None


# ============================================================================
# Global Tracer Tests
# ============================================================================


def test_get_tracer_singleton():
    """get_tracer should return the same instance."""
    reset_tracer()
    tracer1 = get_tracer()
    tracer2 = get_tracer()
    assert tracer1 is tracer2


def test_reset_tracer():
    """reset_tracer should clear the global tracer."""
    tracer1 = get_tracer()
    reset_tracer()
    tracer2 = get_tracer()
    assert tracer1 is not tracer2


# ============================================================================
# Decorator Tests
# ============================================================================


def test_trace_operation_decorator():
    """trace_operation decorator should create spans for function calls."""
    reset_tracer()

    @trace_operation("test.function")
    def test_function():
        return "result"

    result = test_function()
    assert result == "result"


def test_trace_operation_decorator_with_exception():
    """trace_operation decorator should record exceptions."""
    reset_tracer()

    @trace_operation("failing.function")
    def failing_function():
        raise RuntimeError("test error")

    with pytest.raises(RuntimeError):
        failing_function()


def test_trace_operation_decorator_with_correlation():
    """trace_operation decorator should include correlation context."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="test-trace-123",
        project_id="proj1",
        experiment_id="exp1",
    ))

    @trace_operation("test.function")
    def test_function():
        tracer = get_tracer()
        span = tracer.current_span
        assert span is not None
        assert span.attributes["project_id"] == "proj1"
        assert span.attributes["experiment_id"] == "exp1"
        return "result"

    test_function()


# ============================================================================
# Context Manager Tests
# ============================================================================


def test_trace_stage_context_manager():
    """trace_stage should create spans for pipeline stages."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="test-trace-456",
        project_id="proj1",
        experiment_id="exp1",
        run_id="run1",
    ))

    with trace_stage("grading", attributes={"case_version_id": "case1"}) as span:
        assert span is not None
        assert span.attributes["we3.stage"] == "grading"
        assert span.attributes["project_id"] == "proj1"
        assert span.attributes["experiment_id"] == "exp1"
        assert span.attributes["run_id"] == "run1"


def test_trace_stage_exception():
    """trace_stage should handle exceptions."""
    reset_tracer()

    with pytest.raises(ValueError):
        with trace_stage("failing_stage"):
            raise ValueError("stage error")


# ============================================================================
# Propagation Tests
# ============================================================================


def test_propagate_trace_context():
    """propagate_trace_context should add traceparent header."""
    reset_tracer()
    tracer = get_tracer()
    with tracer.start_as_current_span("test.operation"):
        headers = {}
        result = propagate_trace_context(headers)
        assert "traceparent" in result
        assert result["traceparent"].startswith("00-")


def test_extract_trace_context():
    """extract_trace_context should parse traceparent header."""
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    span_id = "b7ad6b7169203331"
    headers = {"traceparent": f"00-{trace_id}-{span_id}-01"}
    result = extract_trace_context(headers)
    assert result is not None
    assert result["trace_id"] == trace_id
    assert result["span_id"] == span_id


def test_with_propagated_context():
    """with_propagated_context should create context from headers."""
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    span_id = "b7ad6b7169203331"
    headers = {
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "X-Correlation-project_id": "proj1",
        "X-Correlation-experiment_id": "exp1",
    }
    context = with_propagated_context(headers)
    assert context.trace_id == trace_id
    assert context.project_id == "proj1"
    assert context.experiment_id == "exp1"


def test_with_propagated_context_no_headers():
    """with_propagated_context should fall back to current context."""
    set_correlation_context(CorrelationContext(trace_id="fallback-trace"))
    context = with_propagated_context({})
    assert context.trace_id == "fallback-trace"


# ============================================================================
# SpanExporter Tests
# ============================================================================


def test_span_exporter_export_empty():
    """SpanExporter should handle empty span lists."""
    exporter = SpanExporter()
    result = exporter.export([])
    assert result.success is True
    assert result.exported_count == 0
    assert result.failed_count == 0


def test_span_exporter_export_with_console():
    """SpanExporter should export spans to console when enabled."""
    config = TracingConfig(console_export=True)
    exporter = SpanExporter(config)
    span = Span(name="test.span", trace_id="trace123", span_id="span456")
    span.end()
    result = exporter.export([span])
    assert result.success is True
    assert result.exported_count == 1


def test_span_exporter_export_without_console():
    """SpanExporter should export spans silently when console is disabled."""
    config = TracingConfig(console_export=False)
    exporter = SpanExporter(config)
    span = Span(name="test.span", trace_id="trace123", span_id="span456")
    span.end()
    result = exporter.export([span])
    assert result.success is True
    assert result.exported_count == 1


def test_span_exporter_shutdown():
    """SpanExporter should support shutdown."""
    exporter = SpanExporter()
    exporter.shutdown()  # Should not raise


# ============================================================================
# Security Tests
# ============================================================================


def test_prohibited_attributes_in_allowlist_check():
    """Prohibited attributes should not be in the allowlist."""
    for attr in PROHIBITED_SPAN_ATTRIBUTES:
        assert attr not in ALLOWED_SPAN_ATTRIBUTES, (
            f"Prohibited attribute '{attr}' should not be in allowlist"
        )


def test_span_rejects_prompt_content():
    """Span should reject prompt/response content attributes."""
    span = Span(name="test.span")
    span.set_attribute("prompt", "what is the meaning of life?")
    span.set_attribute("response", "42")
    span.set_attribute("completion", "the answer is 42")
    span.set_attribute("message", "hello world")
    assert "prompt" not in span.attributes
    assert "response" not in span.attributes
    assert "completion" not in span.attributes
    assert "message" not in span.attributes


def test_span_rejects_secret_values():
    """Span should reject values containing secret patterns."""
    span = Span(name="test.span")
    span.set_attribute("custom_field", "password=secret123")
    span.set_attribute("custom_field2", "api_key=abc123")
    assert "custom_field" not in span.attributes
    assert "custom_field2" not in span.attributes


def test_span_rejects_long_values():
    """Span should reject overly long values."""
    span = Span(name="test.span")
    long_value = "x" * 2000
    span.set_attribute("project_id", long_value)
    assert "project_id" not in span.attributes


# ============================================================================
# Integration with Telemetry Tests
# ============================================================================


def test_tracer_integrates_with_correlation_context():
    """Tracer should integrate with CorrelationContext."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="integration-trace",
        project_id="proj1",
    ))

    tracer = get_tracer()
    with tracer.start_as_current_span("test.operation") as span:
        assert span.trace_id == "integration-trace"


def test_tracer_propagates_trace_id():
    """Tracer should propagate trace_id from correlation context."""
    reset_tracer()
    set_correlation_context(CorrelationContext(trace_id="propagated-trace"))

    tracer = get_tracer()
    span = tracer.start_span("test.operation")
    assert span.trace_id == "propagated-trace"
