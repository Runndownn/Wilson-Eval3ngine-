"""Unit tests for TODO 51 structured telemetry and correlation."""

import os

from wilson_eval3ngine.telemetry import (
    CorrelationContext,
    ALLOWED_LOG_FIELDS,
    ALLOWED_METRIC_NAMES,
    HISTOGRAM_BUCKETS,
    PROHIBITED_PATTERNS,
    redact_sensitive_fields,
    is_safe_for_telemetry,
    TelemetryEvent,
    TelemetryLogger,
    get_correlation_context,
    set_correlation_context,
    SamplingConfig,
    get_sampling_config,
    CANARY_SECRET,
    CANARY_PROMPT,
    TelemetrySpan,
    start_span,
    instrument_operation,
    record_metric,
)


# ============================================================================
# Correlation Context Tests
# ============================================================================

class TestCorrelationContext:
    """Tests for correlation context."""

    def test_context_creation(self):
        """Context can be created with identifiers."""
        ctx = CorrelationContext(
            trace_id="trc_123",
            project_id="proj_1",
            experiment_id="exp_123",
        )
        assert ctx.trace_id == "trc_123"
        assert ctx.project_id == "proj_1"

    def test_context_to_baggage(self):
        """Context converts to baggage format."""
        ctx = CorrelationContext(
            trace_id="trc_123",
            project_id="proj_1",
            experiment_id="exp_123",
        )
        baggage = ctx.to_baggage()
        assert "trace_id" in baggage
        assert baggage["trace_id"] == "trc_123"
        assert baggage["project_id"] == "proj_1"

    def test_context_to_headers(self):
        """Context converts to HTTP header format."""
        ctx = CorrelationContext(trace_id="trc_123", project_id="proj_1")
        headers = ctx.to_headers()
        assert "X-Correlation-trace_id" in headers
        assert headers["X-Correlation-trace_id"] == "trc_123"

    def test_get_correlation_context_returns_default(self):
        """Getting context creates default if missing."""
        # Reset to None
        set_correlation_context(None)
        ctx = get_correlation_context()
        assert ctx.trace_id != ""
        assert ctx.trace_id.startswith("trc_")

    def test_context_child_context(self):
        """Context can create child with overrides."""
        ctx = CorrelationContext(
            trace_id="trc_parent",
            project_id="proj_parent",
        )
        child = ctx.child_context(project_id="proj_child")
        assert child.trace_id == "trc_parent"
        assert child.project_id == "proj_child"


# ============================================================================
# Allowlist Tests
# ============================================================================

class TestAllowlists:
    """Tests for field and metric allowlists."""

    def test_allowed_log_fields_exist(self):
        """Required log fields are in allowlist."""
        assert "trace_id" in ALLOWED_LOG_FIELDS
        assert "experiment_id" in ALLOWED_LOG_FIELDS
        assert "project_id" in ALLOWED_LOG_FIELDS
        assert "run_id" in ALLOWED_LOG_FIELDS
        assert "model_id" in ALLOWED_LOG_FIELDS
        assert "operation" in ALLOWED_LOG_FIELDS

    def test_allowed_metric_names_exist(self):
        """Required metric names are defined."""
        assert "we3.operation.count" in ALLOWED_METRIC_NAMES
        assert "we3.run.duration_ms" in ALLOWED_METRIC_NAMES
        assert "we3.gate.decision" in ALLOWED_METRIC_NAMES

    def test_histogram_buckets_exist(self):
        """Histogram bucket boundaries are defined."""
        assert "duration_ms" in HISTOGRAM_BUCKETS
        buckets = HISTOGRAM_BUCKETS["duration_ms"]
        assert 0 < len(buckets) < 100  # Reasonable number of buckets

    def test_prohibited_patterns_exist(self):
        """Prohibited content patterns are defined."""
        assert "prompt" in PROHIBITED_PATTERNS
        assert "response" in PROHIBITED_PATTERNS
        assert "secret" in PROHIBITED_PATTERNS


# ============================================================================
# Redaction Tests
# ============================================================================

class TestRedaction:
    """Tests for sensitive field redaction."""

    def test_redact_disallowed_fields(self):
        """Disallowed fields are removed from output."""
        data = {
            "trace_id": "trc_123",
            "password": "secret123",
            "count": 5,
        }
        redacted = redact_sensitive_fields(data)
        assert "trace_id" in redacted
        assert "count" in redacted
        assert "password" not in redacted  # Disallowed

    def test_redact_canary_secret(self):
        """Canary secret values are redacted."""
        data = {"trace_id": f"trc_{CANARY_SECRET}"}
        redacted = redact_sensitive_fields(data)
        assert "[REDACTED]" in redacted["trace_id"]

    def test_redact_canary_prompt(self):
        """Canary prompt values are redacted."""
        data = {"run_id": f"{CANARY_PROMPT}"}
        redacted = redact_sensitive_fields(data)
        assert "[REDACTED]" in redacted["run_id"]

    def test_redact_prohibited_field_prompt(self):
        """Prohibited fields like 'prompt' are skipped entirely."""
        data = {"prompt": "This should not appear", "trace_id": "trc_123"}
        redacted = redact_sensitive_fields(data)
        assert "prompt" not in redacted
        assert "trace_id" in redacted

    def test_redact_prohibited_field_response(self):
        """Prohibited fields like 'response' are skipped entirely."""
        data = {"response": "This should not appear", "model_id": "model_1"}
        redacted = redact_sensitive_fields(data)
        assert "response" not in redacted
        assert "model_id" in redacted

    def test_truncate_long_strings(self):
        """Very long strings are truncated."""
        long_text = "x" * 2000
        data = {"text": long_text}
        redacted = redact_sensitive_fields(data)
        assert "text" not in redacted  # Not in allowlist

        # Allowed field with long content gets truncated
        data2 = {"trace_id": long_text}
        redacted2 = redact_sensitive_fields(data2)
        assert "[TRUNCATED]" in redacted2["trace_id"] or len(redacted2["trace_id"]) <= 1024

    def test_is_safe_for_telemetry(self):
        """Safety check works correctly."""
        assert is_safe_for_telemetry("normal text") is True
        assert is_safe_for_telemetry(42) is True
        assert is_safe_for_telemetry(None) is True
        assert is_safe_for_telemetry(CANARY_SECRET) is False
        assert is_safe_for_telemetry("password=secret") is False


# ============================================================================
# Telemetry Event Tests
# ============================================================================

class TestTelemetryEvent:
    """Tests for telemetry event structure."""

    def test_event_creation(self):
        """Event can be created with required fields."""
        event = TelemetryEvent(
            event_type="experiment.started",
            payload={"experiment_id": "exp_123"},
        )
        assert event.event_type == "experiment.started"
        assert "schema_version" not in event.payload

    def test_event_to_log_dict(self):
        """Event converts to log-safe dictionary."""
        event = TelemetryEvent(
            event_type="test_event",
            trace_id="trc_123",
            payload={"count": 5},
        )
        log_dict = event.to_log_dict()
        assert log_dict["event_type"] == "test_event"
        assert log_dict["trace_id"] == "trc_123"
        assert log_dict["schema_version"] == "we3.telemetry_event.v1"

    def test_event_redacts_payload(self):
        """Event payload is redacted."""
        event = TelemetryEvent(
            event_type="test",
            payload={"password": "secret"},
        )
        log_dict = event.to_log_dict()
        assert "password" not in log_dict["payload"]


# ============================================================================
# Telemetry Logger Tests
# ============================================================================

class TestTelemetryLogger:
    """Tests for telemetry logger."""

    def test_logger_creation(self):
        """Logger can be created."""
        logger = TelemetryLogger("test.logger")
        assert logger.logger.name == "test.logger"

    def test_logger_emit_returns_trace_id(self):
        """Emit returns trace_id."""
        logger = TelemetryLogger("test.emit")
        trace_id = logger.emit("test_event", {"count": 1})
        assert trace_id.startswith("trc_")

    def test_logger_event(self):
        """Event method works like OpenTelemetry."""
        logger = TelemetryLogger("test.event")
        trace_id = logger.event("test.span", count=2)
        assert trace_id.startswith("trc_")


# ============================================================================
# Sampling Config Tests
# ============================================================================

class TestSamplingConfig:
    """Tests for sampling configuration."""

    def test_default_sampling(self):
        """Default sampling config exists."""
        config = SamplingConfig()
        assert 0 <= config.traces_sample_rate <= 1

    def test_get_sampling_config(self):
        """Get sampling config returns valid config."""
        config = get_sampling_config()
        assert isinstance(config, SamplingConfig)

    def test_should_sample_trace(self):
        """Sampling decision works."""
        config = SamplingConfig(traces_sample_rate=1.0)
        assert config.should_sample_trace() is True

    def test_should_sample_log(self):
        """Log sampling decision works."""
        config = SamplingConfig(logs_sampling_rate=0.0)
        assert config.should_sample_log() is False


# ============================================================================
# Telemetry Span Tests
# ============================================================================

class TestTelemetrySpan:
    """Tests for telemetry span (OpenTelemetry compatibility)."""

    def test_span_creation(self):
        """Span can be created."""
        span = TelemetrySpan(name="test_span", trace_id="trc_123")
        assert span.name == "test_span"
        assert span.trace_id == "trc_123"
        assert span.is_recording is True

    def test_span_set_attribute(self):
        """Span can set attributes."""
        span = TelemetrySpan(name="test_span", trace_id="trc_123")
        span.set_attribute("count", 42)
        assert span._attributes["count"] == 42

    def test_span_redacts_unsafe_attributes(self):
        """Span redacts unsafe attributes."""
        span = TelemetrySpan(name="test_span", trace_id="trc_123")
        span.set_attribute("secret", "password=secret")
        # Unsafe value should not be set due to safety check
        assert span._attributes.get("secret") is None or "[REDACTED]" in str(span._attributes.get("secret", ""))


# ============================================================================
# Integration Tests
# ============================================================================

class TestTelemetryIntegration:
    """Integration tests for telemetry components."""

    def test_full_correlation_flow(self):
        """Correlation context flows through operations."""
        ctx = CorrelationContext(
            trace_id="trc_test_flow",
            project_id="proj_test",
            experiment_id="exp_flow",
        )
        set_correlation_context(ctx)

        logger = TelemetryLogger("test.flow")
        trace_id = logger.emit("operation.started", {"project_id": "proj_test"})

        assert trace_id == "trc_test_flow"

    def test_context_propagation_headers(self):
        """Headers are correctly formatted for propagation."""
        ctx = CorrelationContext(
            trace_id="trc_abc",
            experiment_id="exp_123",
        )
        headers = ctx.to_headers()
        assert "X-Correlation-trace_id" in headers
        assert "X-Correlation-experiment_id" in headers

    def test_telemetry_disabled_by_env(self):
        """Telemetry can be disabled via environment."""
        os.environ["WE3_TELEMETRY_ENABLED"] = "false"
        logger = TelemetryLogger("test.disabled")
        assert logger._enabled is False
        del os.environ["WE3_TELEMETRY_ENABLED"]

    def test_instrument_operation_decorator(self):
        """instrument_operation decorator works correctly."""
        @instrument_operation
        def sample_operation(x: int) -> int:
            return x * 2

        result = sample_operation(5)
        assert result == 10

    def test_record_metric_validates_name(self):
        """record_metric only allows whitelisted metric names."""
        # Valid metric should work (no exception)
        record_metric("we3.operation.count", 5.0, label="test")
        # Invalid metric should be silently skipped
        record_metric("invalid.metric.name", 5.0)