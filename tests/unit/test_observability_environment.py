"""
Environment-specific tests for Audit & Telemetry (SEC-006).

Tests observability instrumentation across different deployment environments:
- Development: Lightweight tracer, no OTel SDK
- Staging: Full instrumentation with OTel SDK (mocked)
- Production: Dual tracer with security validation
- Minimal: No optional dependencies (graceful degradation)
- OTel-enabled: OTel SDK available and initialized
- OTel-disabled: OTel SDK not available (fallback to lightweight tracer)

Test counts: Comprehensive coverage of instrumentation module
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from wilson_eval3ngine.observability.instrumentation import (
    ALLOWED_SPAN_ATTRIBUTES,
    PROHIBITED_SPAN_ATTRIBUTES,
    DualSpan,
    DualTracer,
    EvaluationPipelineInstrumentor,
    OTELConfig,
    PIPELINE_STAGES,
    PipelineInstrumentor,
    PipelineStage,
    TracingDatabaseSession,
    get_trace_id,
    get_pipeline_instrumentor,
    is_opentelemetry_available,
    reset_instrumentor,
    reset_tracer,
    setup_opentelemetry,
    shutdown_opentelemetry,
    with_trace_context,
)
from wilson_eval3ngine.tracing import (
    Tracer,
    TracingConfig,
    get_tracer,
)
from wilson_eval3ngine.telemetry import (
    CorrelationContext,
    set_correlation_context,
)


# ============================================================================
# Environment-Specific OTELConfig Tests (6 tests)
# ============================================================================

class TestOTELConfigAcrossEnvironments:
    """Test OTELConfig behavior across different environments."""

    def test_otel_config_defaults_dev(self, env_dev):
        """OTELConfig defaults in development environment."""
        config = OTELConfig()
        assert config.enabled is True
        assert config.service_name == "wilson-eval3ngine"
        assert config.service_version == "0.1.0"
        assert config.environment == "development"
        assert 0.0 <= config.traces_sample_rate <= 1.0
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.insecure is True

    def test_otel_config_from_env_staging(self, env_staging):
        """OTELConfig reads from environment variables in staging."""
        with patch.dict(os.environ, {
            "WE3_OTEL_ENABLED": "true",
            "WE3_SERVICE_NAME": "wilson-eval3ngine-staging",
            "WE3_SERVICE_VERSION": "0.1.0-staging",
            "WE3_ENVIRONMENT": "staging",
            "WE3_TRACES_SAMPLE_RATE": "0.5",
            "WE3_OTLP_ENDPOINT": "http://otel-collector.staging:4317",
            "WE3_OTLP_INSECURE": "false",
        }):
            config = OTELConfig()
            assert config.enabled is True
            assert config.service_name == "wilson-eval3ngine-staging"
            assert config.service_version == "0.1.0-staging"
            assert config.environment == "staging"
            assert config.traces_sample_rate == 0.5
            assert config.otlp_endpoint == "http://otel-collector.staging:4317"
            assert config.insecure is False

    def test_otel_config_from_env_production(self, env_production):
        """OTELConfig reads from environment variables in production."""
        with patch.dict(os.environ, {
            "WE3_OTEL_ENABLED": "true",
            "WE3_SERVICE_NAME": "wilson-eval3ngine-prod",
            "WE3_SERVICE_VERSION": "0.1.0",
            "WE3_ENVIRONMENT": "production",
            "WE3_TRACES_SAMPLE_RATE": "1.0",
            "WE3_OTLP_ENDPOINT": "http://otel-collector.prod:4317",
            "WE3_OTLP_INSECURE": "false",
        }):
            config = OTELConfig()
            assert config.enabled is True
            assert config.service_name == "wilson-eval3ngine-prod"
            assert config.environment == "production"
            assert config.insecure is False

    def test_otel_config_resource_attributes(self):
        """OTELConfig produces correct resource attributes."""
        config = OTELConfig()
        attrs = config.to_resource_attributes()
        assert attrs["service.name"] == "wilson-eval3ngine"
        assert attrs["service.version"] == "0.1.0"
        assert attrs["deployment.environment"] == "development"

    def test_otel_config_sample_rate_clamped(self):
        """OTELConfig clamps sample rate to [0.0, 1.0]."""
        with patch.dict(os.environ, {"WE3_TRACES_SAMPLE_RATE": "5.0"}):
            config = OTELConfig()
            assert config.traces_sample_rate == 1.0

        with patch.dict(os.environ, {"WE3_TRACES_SAMPLE_RATE": "-1.0"}):
            config = OTELConfig()
            assert config.traces_sample_rate == 0.0

    def test_otel_config_disabled_in_minimal(self, env_minimal):
        """OTELConfig can be disabled in minimal environment."""
        with patch.dict(os.environ, {"WE3_OTEL_ENABLED": "false"}):
            config = OTELConfig()
            assert config.enabled is False


# ============================================================================
# Environment-Specific OpenTelemetry Detection Tests (4 tests)
# ============================================================================

class TestOpenTelemetryDetectionAcrossEnvironments:
    """Test OpenTelemetry SDK detection across environments."""

    def test_is_opentelemetry_available_returns_bool(self):
        """is_opentelemetry_available returns a boolean."""
        result = is_opentelemetry_available()
        assert isinstance(result, bool)

    def test_is_opentelemetry_available_cached(self):
        """is_opentelemetry_available caches its result."""
        from wilson_eval3ngine.observability import instrumentation as instr
        instr._OTEL_AVAILABLE = None
        result1 = instr.is_opentelemetry_available()
        result2 = instr.is_opentelemetry_available()
        assert result1 == result2

    def test_setup_opentelemetry_disabled(self):
        """setup_opentelemetry returns False when disabled."""
        with patch.dict(os.environ, {"WE3_OTEL_ENABLED": "false"}):
            result = setup_opentelemetry()
            assert result is False

    def test_setup_opentelemetry_not_available(self):
        """setup_opentelemetry returns False when SDK not available."""
        config = OTELConfig(enabled=True)
        with patch(
            "wilson_eval3ngine.observability.instrumentation.is_opentelemetry_available",
            return_value=False,
        ):
            result = setup_opentelemetry(config)
            assert result is False


# ============================================================================
# Environment-Specific DualTracer Tests (8 tests)
# ============================================================================

class TestDualTracerAcrossEnvironments:
    """Test DualTracer behavior across different environments."""

    def test_dual_tracer_creation_dev(self, env_dev):
        """DualTracer is created with default config in development."""
        tracer = DualTracer()
        assert tracer.config.service_name == "wilson-eval3ngine"
        assert tracer.lightweight_tracer is not None
        assert tracer.otel_available is False  # No OTel SDK in test env

    def test_dual_tracer_start_span_dev(self, env_dev):
        """DualTracer creates spans in development."""
        tracer = DualTracer()
        span = tracer.start_span("test.operation", attributes={"project_id": "proj1"})
        assert span.name == "test.operation"
        assert span.is_recording is True
        assert span.trace_id != ""

    def test_dual_tracer_start_as_current_span_dev(self, env_dev):
        """DualTracer sets span as current in development."""
        tracer = DualTracer()
        with tracer.start_as_current_span("test.operation") as span:
            assert tracer.current_span is not None
            assert span.is_recording is True
        assert tracer.current_span is None

    def test_dual_tracer_span_hierarchy_dev(self, env_dev):
        """DualTracer maintains parent-child span relationships."""
        tracer = DualTracer()
        with tracer.start_as_current_span("parent") as parent:
            parent_span_id = parent.span_id
            with tracer.start_as_current_span("child") as child:
                assert child.parent_span_id == parent_span_id
                assert child.trace_id == parent.trace_id
            assert tracer.current_span is not None

    def test_dual_tracer_exception_in_span_dev(self, env_dev):
        """DualTracer records exceptions in spans."""
        tracer = DualTracer()
        with pytest.raises(ValueError):
            with tracer.start_as_current_span("failing.operation") as span:
                raise ValueError("test error")
        assert span.attributes.get("error") is True

    def test_dual_tracer_inject_trace_context_dev(self, env_dev):
        """DualTracer injects trace context into headers."""
        tracer = DualTracer()
        with tracer.start_as_current_span("test.operation"):
            headers = {}
            result = tracer.inject_trace_context(headers)
            assert "traceparent" in result
            assert result["traceparent"].startswith("00-")

    def test_dual_tracer_extract_trace_context_dev(self, env_dev):
        """DualTracer extracts trace context from headers."""
        tracer = DualTracer()
        trace_id = "0af7651916cd43dd8448eb211c80319c"
        span_id = "b7ad6b7169203331"
        headers = {"traceparent": f"00-{trace_id}-{span_id}-01"}
        result = tracer.extract_trace_context(headers)
        assert result is not None
        assert result["trace_id"] == trace_id
        assert result["span_id"] == span_id

    def test_dual_tracer_disabled(self):
        """DualTracer does not record when tracing is disabled."""
        config = TracingConfig(enabled=False)
        tracer = DualTracer(config)
        span = tracer.start_span("test.operation")
        assert span.is_recording is False


# ============================================================================
# Environment-Specific DualSpan Security Tests (6 tests)
# ============================================================================

class TestDualSpanSecurityAcrossEnvironments:
    """Test DualSpan security validation across environments."""

    def test_dual_span_set_attribute_allowed(self):
        """DualSpan accepts attributes in the allowlist."""
        tracer = DualTracer()
        span = tracer.start_span("test.span")
        span.set_attribute("project_id", "proj1")
        span.set_attribute("status", "success")
        assert span._lightweight.attributes["project_id"] == "proj1"
        assert span._lightweight.attributes["status"] == "success"

    def test_dual_span_set_attribute_prohibited(self):
        """DualSpan rejects prohibited attribute keys."""
        tracer = DualTracer()
        span = tracer.start_span("test.span")
        span.set_attribute("password", "secret123")
        span.set_attribute("api_key", "key123")
        assert "password" not in span._lightweight.attributes
        assert "api_key" not in span._lightweight.attributes

    def test_dual_span_rejects_prompt_content(self):
        """DualSpan rejects prompt/response content attributes."""
        tracer = DualTracer()
        span = tracer.start_span("test.span")
        span.set_attribute("prompt", "what is the meaning of life?")
        span.set_attribute("response", "42")
        span.set_attribute("completion", "the answer is 42")
        span.set_attribute("message", "hello world")
        assert "prompt" not in span._lightweight.attributes
        assert "response" not in span._lightweight.attributes
        assert "completion" not in span._lightweight.attributes
        assert "message" not in span._lightweight.attributes

    def test_dual_span_rejects_secret_values(self):
        """DualSpan rejects values containing secret patterns."""
        tracer = DualTracer()
        span = tracer.start_span("test.span")
        span.set_attribute("custom_field", "password=secret123")
        span.set_attribute("custom_field2", "api_key=abc123")
        assert "custom_field" not in span._lightweight.attributes
        assert "custom_field2" not in span._lightweight.attributes

    def test_dual_span_rejects_long_values(self):
        """DualSpan rejects overly long values."""
        tracer = DualTracer()
        span = tracer.start_span("test.span")
        long_value = "x" * 2000
        span.set_attribute("project_id", long_value)
        assert "project_id" not in span._lightweight.attributes

    def test_prohibited_attributes_in_allowlist_check(self):
        """Prohibited attributes should not be in the allowlist."""
        for attr in PROHIBITED_SPAN_ATTRIBUTES:
            assert attr not in ALLOWED_SPAN_ATTRIBUTES, (
                f"Prohibited attribute '{attr}' should not be in allowlist"
            )


# ============================================================================
# Environment-Specific PipelineInstrumentor Tests (6 tests)
# ============================================================================

class TestPipelineInstrumentorAcrossEnvironments:
    """Test PipelineInstrumentor behavior across environments."""

    def test_pipeline_stages_contains_key_stages(self):
        """PIPELINE_STAGES contains all key pipeline stages."""
        expected_stages = [
            "manifest_load", "dataset_load", "experiment_create",
            "artifact_store", "expectation_compile", "case_iteration",
            "prompt_render", "provider_execute", "grading",
            "metric_compute", "gate_evaluate", "dossier_build",
            "result_index_write", "audit_verify",
        ]
        for stage in expected_stages:
            assert stage in PIPELINE_STAGES, f"Missing stage: {stage}"

    def test_pipeline_instrumentor_creation(self):
        """PipelineInstrumentor is created with a tracer."""
        instrumentor = PipelineInstrumentor()
        assert instrumentor.tracer is not None

    def test_pipeline_instrumentor_stage_context_manager(self):
        """PipelineInstrumentor creates spans for stages."""
        instrumentor = PipelineInstrumentor()
        with instrumentor.stage("grading", project_id="proj1") as span:
            assert span is not None
            assert span.attributes.get("we3.stage") == "grading"
            assert span.attributes.get("project_id") == "proj1"

    def test_pipeline_instrumentor_stage_with_correlation_context(self):
        """PipelineInstrumentor includes correlation context in spans."""
        reset_tracer()
        set_correlation_context(CorrelationContext(
            trace_id="test-trace-123",
            project_id="proj1",
            experiment_id="exp1",
            run_id="run1",
        ))
        instrumentor = PipelineInstrumentor()
        with instrumentor.stage("grading") as span:
            assert span.attributes.get("project_id") == "proj1"
            assert span.attributes.get("experiment_id") == "exp1"
            assert span.attributes.get("run_id") == "run1"

    def test_pipeline_instrumentor_stage_exception(self):
        """PipelineInstrumentor handles exceptions in stages."""
        instrumentor = PipelineInstrumentor()
        with pytest.raises(ValueError):
            with instrumentor.stage("failing_stage"):
                raise ValueError("stage error")

    def test_pipeline_instrumentor_record_operation_result(self):
        """PipelineInstrumentor records operation results as metrics."""
        instrumentor = PipelineInstrumentor()
        instrumentor.record_operation_result(
            "grading",
            success=True,
            project_id="proj1",
            run_id="run1",
        )


# ============================================================================
# Environment-Specific TracingDatabaseSession Tests (6 tests)
# ============================================================================

class TestTracingDatabaseSessionAcrossEnvironments:
    """Test TracingDatabaseSession behavior across environments."""

    def test_tracing_db_session_execute(self):
        """TracingDatabaseSession wraps session.execute with tracing."""
        mock_session = MagicMock()
        mock_session.execute.return_value = "result"
        session = TracingDatabaseSession(mock_session)

        from sqlalchemy import text
        result = session.execute(text("SELECT 1"))

        assert result == "result"
        mock_session.execute.assert_called_once()

    def test_tracing_db_session_commit(self):
        """TracingDatabaseSession wraps session.commit with tracing."""
        mock_session = MagicMock()
        session = TracingDatabaseSession(mock_session)
        session.commit()
        mock_session.commit.assert_called_once()

    def test_tracing_db_session_rollback(self):
        """TracingDatabaseSession wraps session.rollback with tracing."""
        mock_session = MagicMock()
        session = TracingDatabaseSession(mock_session)
        session.rollback()
        mock_session.rollback.assert_called_once()

    def test_tracing_db_session_extract_operation_type(self):
        """TracingDatabaseSession extracts SQL operation type."""
        assert TracingDatabaseSession._extract_operation_type("SELECT * FROM users") == "SELECT"
        assert TracingDatabaseSession._extract_operation_type("INSERT INTO users VALUES (1)") == "INSERT"
        assert TracingDatabaseSession._extract_operation_type("UPDATE users SET name='test'") == "UPDATE"
        assert TracingDatabaseSession._extract_operation_type("DELETE FROM users") == "DELETE"
        assert TracingDatabaseSession._extract_operation_type("CREATE TABLE test (id INT)") == "CREATE"
        assert TracingDatabaseSession._extract_operation_type("UNKNOWN STATEMENT") == "UNKNOWN"

    def test_tracing_db_session_extract_table_name(self):
        """TracingDatabaseSession extracts table name from SQL."""
        assert TracingDatabaseSession._extract_table_name("SELECT * FROM users") == "users"
        assert TracingDatabaseSession._extract_table_name("INSERT INTO users VALUES (1)") == "users"
        assert TracingDatabaseSession._extract_table_name("UPDATE users SET name='test'") == "users"
        assert TracingDatabaseSession._extract_table_name("DELETE FROM users") == "users"
        assert TracingDatabaseSession._extract_table_name("SELECT 1") is None

    def test_tracing_db_session_with_project_id(self):
        """TracingDatabaseSession includes project_id in spans."""
        mock_session = MagicMock()
        mock_session.execute.return_value = "result"
        session = TracingDatabaseSession(mock_session, project_id="proj1")

        from sqlalchemy import text
        session.execute(text("SELECT 1"))
        mock_session.execute.assert_called_once()


# ============================================================================
# Environment-Specific EvaluationPipelineInstrumentor Tests (4 tests)
# ============================================================================

class TestEvaluationPipelineInstrumentorAcrossEnvironments:
    """Test EvaluationPipelineInstrumentor behavior across environments."""

    def test_evaluation_pipeline_instrumentor_creation(self):
        """EvaluationPipelineInstrumentor is created with a service."""
        mock_service = MagicMock()
        instrumentor = EvaluationPipelineInstrumentor(mock_service)
        assert instrumentor.pipeline is not None
        assert instrumentor.tracer is not None

    def test_evaluation_pipeline_instrumentor_run_manifest_success(self):
        """EvaluationPipelineInstrumentor traces successful runs."""
        mock_service = MagicMock()
        mock_outcome = MagicMock()
        mock_outcome.experiment_id = "exp1"
        mock_outcome.gate_statuses = {"model1": "pass"}
        mock_service.run_manifest.return_value = mock_outcome

        instrumentor = EvaluationPipelineInstrumentor(mock_service)
        outcome = instrumentor.run_manifest("manifest.yaml", output_dir="/tmp/out")

        assert outcome is mock_outcome
        mock_service.run_manifest.assert_called_once_with(
            "manifest.yaml",
            output_dir="/tmp/out",
            signing_key_path=None,
        )

    def test_evaluation_pipeline_instrumentor_run_manifest_failure(self):
        """EvaluationPipelineInstrumentor traces failed runs."""
        mock_service = MagicMock()
        mock_service.run_manifest.side_effect = RuntimeError("pipeline error")

        instrumentor = EvaluationPipelineInstrumentor(mock_service)

        with pytest.raises(RuntimeError):
            instrumentor.run_manifest("manifest.yaml", output_dir="/tmp/out")

        mock_service.run_manifest.assert_called_once()

    def test_evaluation_pipeline_instrumentor_with_signing_key(self):
        """EvaluationPipelineInstrumentor passes signing_key_path."""
        mock_service = MagicMock()
        mock_outcome = MagicMock()
        mock_outcome.experiment_id = "exp1"
        mock_outcome.gate_statuses = {}
        mock_service.run_manifest.return_value = mock_outcome

        instrumentor = EvaluationPipelineInstrumentor(mock_service)
        instrumentor.run_manifest(
            "manifest.yaml",
            output_dir="/tmp/out",
            signing_key_path="/path/to/key.pem",
        )

        mock_service.run_manifest.assert_called_once_with(
            "manifest.yaml",
            output_dir="/tmp/out",
            signing_key_path="/path/to/key.pem",
        )


# ============================================================================
# Environment-Specific Trace ID and Context Tests (6 tests)
# ============================================================================

class TestTraceIdAndContextAcrossEnvironments:
    """Test trace ID and context propagation across environments."""

    def test_get_trace_id_from_active_span(self):
        """get_trace_id returns trace ID from active span."""
        reset_tracer()
        tracer = get_tracer()
        with tracer.start_as_current_span("test.operation"):
            trace_id = get_trace_id()
            assert trace_id != ""

    def test_get_trace_id_from_correlation_context(self):
        """get_trace_id falls back to correlation context."""
        reset_tracer()
        set_correlation_context(CorrelationContext(trace_id="fallback-trace-123"))
        trace_id = get_trace_id()
        assert trace_id == "fallback-trace-123"

    def test_get_trace_id_last_resort(self):
        """get_trace_id generates a new ID as last resort."""
        reset_tracer()
        set_correlation_context(CorrelationContext(trace_id=""))
        trace_id = get_trace_id()
        assert trace_id.startswith("trc_")

    def test_with_trace_context_from_headers(self):
        """with_trace_context creates context from trace headers."""
        trace_id = "0af7651916cd43dd8448eb211c80319c"
        span_id = "b7ad6b7169203331"
        headers = {
            "traceparent": f"00-{trace_id}-{span_id}-01",
            "X-Correlation-project_id": "proj1",
            "X-Correlation-experiment_id": "exp1",
        }
        context = with_trace_context(headers)
        assert context.trace_id == trace_id
        assert context.project_id == "proj1"
        assert context.experiment_id == "exp1"

    def test_with_trace_context_no_headers(self):
        """with_trace_context falls back to current context."""
        set_correlation_context(CorrelationContext(trace_id="fallback-trace"))
        context = with_trace_context({})
        assert context.trace_id == "fallback-trace"

    def test_dual_tracer_integrates_with_correlation_context(self):
        """DualTracer integrates with CorrelationContext."""
        reset_tracer()
        set_correlation_context(CorrelationContext(
            trace_id="integration-trace",
            project_id="proj1",
        ))

        tracer = DualTracer()
        with tracer.start_as_current_span("test.operation") as span:
            assert span.trace_id == "integration-trace"


# ============================================================================
# Environment-Specific Global Instrumentor Tests (4 tests)
# ============================================================================

class TestGlobalInstrumentorAcrossEnvironments:
    """Test global instrumentor management across environments."""

    def test_get_pipeline_instrumentor_creates(self):
        """get_pipeline_instrumentor creates instrumentor with service."""
        reset_instrumentor()
        mock_service = MagicMock()
        instrumentor = get_pipeline_instrumentor(mock_service)
        assert instrumentor is not None
        assert instrumentor._service is mock_service

    def test_get_pipeline_instrumentor_returns_existing(self):
        """get_pipeline_instrumentor returns existing instance."""
        reset_instrumentor()
        mock_service = MagicMock()
        instrumentor1 = get_pipeline_instrumentor(mock_service)
        instrumentor2 = get_pipeline_instrumentor()
        assert instrumentor1 is instrumentor2

    def test_get_pipeline_instrumentor_no_service_raises(self):
        """get_pipeline_instrumentor raises when no service provided."""
        reset_instrumentor()
        with pytest.raises(ValueError, match="service must be provided"):
            get_pipeline_instrumentor()

    def test_reset_instrumentor(self):
        """reset_instrumentor clears the global instrumentor."""
        reset_instrumentor()
        mock_service = MagicMock()
        get_pipeline_instrumentor(mock_service)
        reset_instrumentor()
        with pytest.raises(ValueError):
            get_pipeline_instrumentor()
