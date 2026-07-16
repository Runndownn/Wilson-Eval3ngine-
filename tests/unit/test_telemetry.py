"""Unit tests for TODO 51 structured telemetry and correlation."""

from wilson_eval3ngine.telemetry import (
    CorrelationContext,
    ALLOWED_LOG_FIELDS,
    ALLOWED_METRIC_NAMES,
    HISTOGRAM_BUCKETS,
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
        # Use a field that IS in ALLOWED_LOG_FIELDS
        data = {"trace_id": f"trc_{CANARY_SECRET}"}
        redacted = redact_sensitive_fields(data)
        assert "[REDACTED]" in redacted["trace_id"]

    def test_redact_canary_prompt(self):
        """Canary prompt values are redacted."""
        # Use a field that IS in ALLOWED_LOG_FIELDS
        data = {"run_id": f"{CANARY_PROMPT}"}
        redacted = redact_sensitive_fields(data)
        assert "[REDACTED]" in redacted["run_id"]

    def test_redact_secret_patterns(self):
        """Secret patterns are redacted."""
        data = {"value": "api_key=secret123"}
        redacted = redact_sensitive_fields(data)
        assert "[REDACTED]" in redacted["value"]

    def test_truncate_long_strings(self):
        """Very long strings are truncated."""
        long_text = "x" * 2000
        # "text" is not in ALLOWED_LOG_FIELDS, so it's removed
        data = {"text": long_text}
        redacted = redact_sensitive_fields(data)
        assert "text" not in redacted

        # But if we use an allowed field with long content
        data2 = {"trace_id": long_text}
        redacted2 = redact_sensitive_fields(data2)
        assert "[TRUNCATED]" in redacted2["trace_id"] or redacted2["trace_id"] == long_text[:1024]

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
        assert "schema_version" not in event.payload  # In to_log_dict

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
        # With rate 1.0, should always sample
        assert config.should_sample_trace() is True

    def test_should_sample_log(self):
        """Log sampling decision works."""
        config = SamplingConfig(logs_sampling_rate=0.0)
        assert config.should_sample_log() is False


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
        import os
        os.environ["WE3_TELEMETRY_ENABLED"] = "false"
        logger = TelemetryLogger("test.disabled")
        assert logger._enabled is False
        del os.environ["WE3_TELEMETRY_ENABLED"]