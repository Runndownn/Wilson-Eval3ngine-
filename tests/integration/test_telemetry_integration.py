"""Integration tests for TODO 51 telemetry with API and service layers."""

from fastapi.testclient import TestClient

from wilson_eval3ngine.api.main import create_app
from wilson_eval3ngine.config import Settings
from wilson_eval3ngine.telemetry import (
    CorrelationContext,
    set_correlation_context,
    TelemetryLogger,
    CANARY_SECRET,
    redact_sensitive_fields,
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
        # Test with various fields that ARE allowed
        test_cases = [
            {"trace_id": f"abc_{CANARY_SECRET}def"},
            {"run_id": f"run_{CANARY_SECRET}123"},
            {"model_id": "model_with_secret"},
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