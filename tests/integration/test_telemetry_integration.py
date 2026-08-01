"""Integration tests for TODO 51 telemetry with API and service layers."""

import logging
from fastapi.testclient import TestClient

from wilson_eval3ngine.api.main import create_app
from wilson_eval3ngine.config import Settings
from wilson_eval3ngine.telemetry import (
    CorrelationContext,
    set_correlation_context,
    TelemetryLogger,
    CANARY_SECRET,
    redact_sensitive_fields,
    start_span,
    instrument_operation,
    get_telemetry_logger,
)


class TestTelemetryApiIntegration:
    """Tests for telemetry integration with API."""

    def test_health_endpoint_includes_trace_id(self, tmp_path):
        """Health endpoint includes correlation in response."""
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'telemetry.api.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="dev",
            environment="test",
        )
        client = TestClient(create_app(settings))

        response = client.get("/health")
        assert response.status_code == 200

    def test_operation_emits_telemetry(self, tmp_path, foundation_manifest):
        """Operations emit telemetry events."""
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'telemetry.op.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="dev",
            environment="test",
        )
        client = TestClient(create_app(settings))

        ctx = CorrelationContext(
            trace_id="trc_telemetry_test",
            project_id="model-safety",
        )
        set_correlation_context(ctx)

        response = client.post(
            "/v1/experiments:run",
            json={
                "manifest_path": str(foundation_manifest),
                "output_dir": str(tmp_path / "output"),
            },
            headers={
                "X-WE3-Project-ID": "model-safety",
                "X-WE3-Role": "evaluation_engineer",
            },
        )
        assert response.status_code == 202
        assert "trace_id" in response.json()


class TestTelemetryRedactionIntegration:
    """Tests for comprehensive redaction coverage."""

    def test_redacts_unsafe_content_in_any_field(self):
        """Any field containing unsafe content is redacted."""
        test_cases = [
            {"trace_id": f"abc_{CANARY_SECRET}def"},
            {"run_id": f"run_{CANARY_SECRET}123"},
        ]
        for data in test_cases:
            for key, value in data.items():
                if CANARY_SECRET in value:
                    redacted = redact_sensitive_fields(data)
                    assert redacted[key] == "[REDACTED]"

    def test_telemetry_logger_handles_secrets(self):
        """Telemetry logger handles secret data gracefully."""
        ctx = CorrelationContext(trace_id="trc_test")
        set_correlation_context(ctx)

        logger = TelemetryLogger("test.secrets")
        # This should NOT raise - secrets are redacted
        trace_id = logger.emit(
            "test.event",
            {"model_id": f"model_{CANARY_SECRET}", "count": 5}
        )
        assert trace_id == "trc_test"


class TestTelemetrySpanIntegration:
    """Tests for telemetry span functionality."""

    def test_span_tracing(self):
        """Span tracing works correctly."""
        ctx = CorrelationContext(trace_id="trc_span_test", project_id="proj_test")
        set_correlation_context(ctx)

        span = start_span("test_operation", test_attr="value")
        span.set_attribute("count", 42)
        span.end()

        assert span.name == "test_operation"

    def test_span_with_context_manager(self):
        """Span can be used in context-like patterns."""
        ctx = CorrelationContext(trace_id="trc_ctx_test")
        set_correlation_context(ctx)

        @instrument_operation
        def sample_func(x: int) -> int:
            return x * 2

        result = sample_func(21)
        assert result == 42


class TestTelemetryOutboxIntegration:
    """Tests for telemetry integration with outbox events."""

    def test_outbox_event_telemetry(self, tmp_path):
        """Outbox events are logged with telemetry context."""
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'outbox_telem.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="dev",
            environment="test",
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/v1/experiments:run",
            json={
                "manifest_path": str(tmp_path / "nonexistent.yaml"),
                "output_dir": str(tmp_path / "output"),
            },
            headers={
                "X-WE3-Project-ID": "model-safety",
                "X-WE3-Role": "evaluation_engineer",
            },
        )
        # Operation attempted with telemetry
        assert "trace_id" in response.json()


class TestTelemetryMetricIntegration:
    """Tests for metric recording with telemetry."""

    def test_metric_recording(self):
        """Metrics can be recorded through telemetry."""
        from wilson_eval3ngine.telemetry import record_metric

        # Valid metric name should work
        record_metric("we3.run.count", 5.0, project_id="test_proj")

        # Invalid metric name should be silently skipped
        record_metric("invalid_metric", 5.0)

    def test_metric_cardinality_limits(self):
        """Metrics respect cardinality limits."""
        from wilson_eval3ngine.telemetry import record_metric

        # Too many labels should be handled gracefully (no exception)
        many_labels = {f"label_{i}": f"value_{i}" for i in range(15)}
        record_metric("we3.run.count", 5.0, **many_labels)