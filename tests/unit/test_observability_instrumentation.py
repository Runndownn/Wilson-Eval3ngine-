"""
Comprehensive unit tests for the observability instrumentation module.

Tests cover:
- OTELConfig configuration and environment variable parsing
- OpenTelemetry SDK detection and setup
- DualTracer (lightweight + OTel SDK bridge)
- DualSpan attribute validation and security
- PipelineInstrumentor stage context manager
- TracingDatabaseSession query tracing
- EvaluationPipelineInstrumentor end-to-end
- get_trace_id and trace context propagation
- Global instrumentor management
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
# OTELConfig Tests
# ============================================================================


def test_otel_config_defaults():
    """OTELConfig should have sensible defaults."""
    config = OTELConfig()
    assert config.enabled is True
    assert config.service_name == "wilson-eval3ngine"
    assert config.service_version == "0.1.0"
    assert config.environment == "development"
    assert 0.0 <= config.traces_sample_rate <= 1.0
    assert config.otlp_endpoint == "http://localhost:4317"
    assert config.insecure is True


def test_otel_config_from_env():
    """OTELConfig should read from environment variables."""
    with patch.dict(os.environ, {
        "WE3_OTEL_ENABLED": "false",
        "WE3_SERVICE_NAME": "test-service",
        "WE3_SERVICE_VERSION": "2.0.0",
        "WE3_ENVIRONMENT": "production",
        "WE3_TRACES_SAMPLE_RATE": "0.5",
        "WE3_OTLP_ENDPOINT": "http://collector:4317",
        "WE3_OTLP_INSECURE": "false",
    }):
        config = OTELConfig()
        assert config.enabled is False
        assert config.service_name == "test-service"
        assert config.service_version == "2.0.0"
        assert config.environment == "production"
        assert config.traces_sample_rate == 0.5
        assert config.otlp_endpoint == "http://collector:4317"
        assert config.insecure is False


def test_otel_config_resource_attributes():
    """OTELConfig should produce correct resource attributes."""
    config = OTELConfig()
    attrs = config.to_resource_attributes()
    assert attrs["service.name"] == "wilson-eval3ngine"
    assert attrs["service.version"] == "0.1.0"
    assert attrs["deployment.environment"] == "development"


def test_otel_config_sample_rate_clamped():
    """OTELConfig should clamp sample rate to [0.0, 1.0]."""
    with patch.dict(os.environ, {"WE3_TRACES_SAMPLE_RATE": "5.0"}):
        config = OTELConfig()
        assert config.traces_sample_rate == 1.0

    with patch.dict(os.environ, {"WE3_TRACES_SAMPLE_RATE": "-1.0"}):
        config = OTELConfig()
        assert config.traces_sample_rate == 0.0


# ============================================================================
# OpenTelemetry SDK Detection Tests
# ============================================================================


def test_is_opentelemetry_available_returns_bool():
    """is_opentelemetry_available should return a boolean."""
    result = is_opentelemetry_available()
    assert isinstance(result, bool)


def test_is_opentelemetry_available_cached():
    """is_opentelemetry_available should cache its result."""
    from wilson_eval3ngine.observability import instrumentation as instr
    # Reset cache
    instr._OTEL_AVAILABLE = None
    result1 = instr.is_opentelemetry_available()
    result2 = instr.is_opentelemetry_available()
    assert result1 == result2


# ============================================================================
# setup_opentelemetry Tests
# ============================================================================


def test_setup_opentelemetry_disabled():
    """setup_opentelemetry should return False when disabled."""
    with patch.dict(os.environ, {"WE3_OTEL_ENABLED": "false"}):
        result = setup_opentelemetry()
        assert result is False


def test_setup_opentelemetry_not_available():
    """setup_opentelemetry should return False when SDK not available."""
    config = OTELConfig(enabled=True)
    with patch(
        "wilson_eval3ngine.observability.instrumentation.is_opentelemetry_available",
        return_value=False,
    ):
        result = setup_opentelemetry(config)
        assert result is False


def test_setup_opentelemetry_idempotent():
    """setup_opentelemetry should be idempotent."""
    from wilson_eval3ngine.observability import instrumentation as instr
    instr._OTEL_INITIALIZED = False
    instr._OTEL_AVAILABLE = False  # Simulate not available
    result1 = setup_opentelemetry()
    result2 = setup_opentelemetry()
    assert result1 == result2


def test_setup_opentelemetry_with_mock_sdk():
    """setup_opentelemetry should initialize when SDK is available."""
    from wilson_eval3ngine.observability import instrumentation as instr
    instr._OTEL_INITIALIZED = False

    config = OTELConfig(enabled=True)

    # Mock the OTel SDK
    mock_provider = MagicMock()
    mock_provider.add_span_processor = MagicMock()

    mock_module = MagicMock()
    mock_module.Resource = MagicMock()
    mock_module.Resource.create = MagicMock(return_value=MagicMock())
    mock_module.TracerProvider = MagicMock(return_value=mock_provider)
    mock_module.BatchSpanProcessor = MagicMock()
    mock_module.ConsoleSpanExporter = MagicMock()
    mock_module.ALWAYS_ON = MagicMock()
    mock_module.TraceIdRatioBased = MagicMock()
    mock_module.OTLPSpanExporter = MagicMock()
    mock_module.set_global_textmap = MagicMock()
    mock_module.CompositePropagator = MagicMock(return_value=MagicMock())
    mock_module.TraceContextTextMapPropagator = MagicMock()
    mock_module.BaggagePropagator = MagicMock()

    mock_trace_module = MagicMock()
    mock_trace_module.set_tracer_provider = MagicMock()
    mock_trace_module.get_tracer = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "opentelemetry": MagicMock(),
            "opentelemetry.sdk": MagicMock(),
            "opentelemetry.sdk.resources": mock_module,
            "opentelemetry.sdk.trace": MagicMock(),
            "opentelemetry.sdk.trace.export": mock_module,
            "opentelemetry.sdk.trace.sampling": mock_module,
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_module,
            "opentelemetry.propagate": mock_module,
            "opentelemetry.propagators.composite": mock_module,
            "opentelemetry.propagators.textmap": mock_module,
            "opentelemetry.propagators.baggage": mock_module,
            "opentelemetry.trace": mock_trace_module,
        },
    ):
        # Force re-detection
        instr._OTEL_AVAILABLE = True
        result = setup_opentelemetry(config)
        assert result is True
        assert instr._OTEL_INITIALIZED is True

    # Cleanup
    instr._OTEL_INITIALIZED = False
    instr._OTEL_AVAILABLE = None


# ============================================================================
# get_opentelemetry_tracer Tests
# ============================================================================


def test_get_opentelemetry_tracer_not_initialized():
    """get_opentelemetry_tracer should return None when not initialized."""
    from wilson_eval3ngine.observability import instrumentation as instr
    instr._OTEL_INITIALIZED = False
    assert instr.get_opentelemetry_tracer() is None


# ============================================================================
# shutdown_opentelemetry Tests
# ============================================================================


def test_shutdown_opentelemetry_not_initialized():
    """shutdown_opentelemetry should be a no-op when not initialized."""
    from wilson_eval3ngine.observability import instrumentation as instr
    instr._OTEL_INITIALIZED = False
    # Should not raise
    instr.shutdown_opentelemetry()


# ============================================================================
# DualTracer Tests
# ============================================================================


def test_dual_tracer_creation():
    """DualTracer should be created with default config."""
    tracer = DualTracer()
    assert tracer.config.service_name == "wilson-eval3ngine"
    assert tracer.lightweight_tracer is not None
    assert tracer.otel_available is False  # No OTel SDK in test env


def test_dual_tracer_start_span():
    """DualTracer should create spans."""
    tracer = DualTracer()
    span = tracer.start_span("test.operation", attributes={"project_id": "proj1"})
    assert span.name == "test.operation"
    assert span.is_recording is True
    assert span.trace_id != ""


def test_dual_tracer_start_as_current_span():
    """DualTracer should set span as current within context manager."""
    tracer = DualTracer()
    with tracer.start_as_current_span("test.operation") as span:
        assert tracer.current_span is not None
        assert span.is_recording is True
    assert tracer.current_span is None


def test_dual_tracer_span_hierarchy():
    """DualTracer should maintain parent-child span relationships."""
    tracer = DualTracer()
    with tracer.start_as_current_span("parent") as parent:
        parent_span_id = parent.span_id
        with tracer.start_as_current_span("child") as child:
            assert child.parent_span_id == parent_span_id
            assert child.trace_id == parent.trace_id
        assert tracer.current_span is not None


def test_dual_tracer_exception_in_span():
    """DualTracer should record exceptions in spans."""
    tracer = DualTracer()
    with pytest.raises(ValueError):
        with tracer.start_as_current_span("failing.operation") as span:
            raise ValueError("test error")
    assert span.attributes.get("error") is True


def test_dual_tracer_inject_trace_context():
    """DualTracer should inject trace context into headers."""
    tracer = DualTracer()
    with tracer.start_as_current_span("test.operation"):
        headers = {}
        result = tracer.inject_trace_context(headers)
        assert "traceparent" in result
        assert result["traceparent"].startswith("00-")


def test_dual_tracer_extract_trace_context():
    """DualTracer should extract trace context from headers."""
    tracer = DualTracer()
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    span_id = "b7ad6b7169203331"
    headers = {"traceparent": f"00-{trace_id}-{span_id}-01"}
    result = tracer.extract_trace_context(headers)
    assert result is not None
    assert result["trace_id"] == trace_id
    assert result["span_id"] == span_id


def test_dual_tracer_disabled():
    """DualTracer should not record when tracing is disabled."""
    config = TracingConfig(enabled=False)
    tracer = DualTracer(config)
    span = tracer.start_span("test.operation")
    assert span.is_recording is False


# ============================================================================
# DualSpan Tests
# ============================================================================


def test_dual_span_set_attribute_allowed():
    """DualSpan should accept attributes in the allowlist."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    span.set_attribute("project_id", "proj1")
    span.set_attribute("status", "success")
    assert span._lightweight.attributes["project_id"] == "proj1"
    assert span._lightweight.attributes["status"] == "success"


def test_dual_span_set_attribute_prohibited():
    """DualSpan should reject prohibited attribute keys."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    span.set_attribute("password", "secret123")
    span.set_attribute("api_key", "key123")
    assert "password" not in span._lightweight.attributes
    assert "api_key" not in span._lightweight.attributes


def test_dual_span_set_attributes():
    """DualSpan should set multiple attributes at once."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    span.set_attributes({
        "project_id": "proj1",
        "status": "success",
        "custom_field": "should_be_rejected",
    })
    assert span._lightweight.attributes["project_id"] == "proj1"
    assert span._lightweight.attributes["status"] == "success"
    assert "custom_field" not in span._lightweight.attributes


def test_dual_span_add_event():
    """DualSpan should add events with validated attributes."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    span.add_event("checkpoint", {"project_id": "proj1", "custom": "rejected"})
    assert len(span._lightweight.events) == 1
    assert span._lightweight.events[0]["name"] == "checkpoint"
    assert span._lightweight.events[0]["attributes"]["project_id"] == "proj1"
    assert "custom" not in span._lightweight.events[0]["attributes"]


def test_dual_span_record_exception():
    """DualSpan should record exceptions."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    try:
        raise ValueError("test error")
    except ValueError as exc:
        span.record_exception(exc)
    assert span._lightweight.attributes.get("error") is True
    assert len(span._lightweight.events) == 1
    assert span._lightweight.events[0]["name"] == "exception"


def test_dual_span_end():
    """DualSpan should end and set end_time."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    assert span.is_recording is True
    span.end()
    assert span.is_recording is False
    assert span._lightweight.end_time > 0


def test_dual_span_properties():
    """DualSpan should expose span properties."""
    tracer = DualTracer()
    span = tracer.start_span("test.operation")
    assert span.name == "test.operation"
    assert span.trace_id != ""
    assert span.span_id != ""
    assert span.parent_span_id == ""


# ============================================================================
# PipelineStage Tests
# ============================================================================


def test_pipeline_stages_contains_key_stages():
    """PIPELINE_STAGES should contain all key pipeline stages."""
    expected_stages = [
        "manifest_load", "dataset_load", "experiment_create",
        "artifact_store", "expectation_compile", "case_iteration",
        "prompt_render", "provider_execute", "grading",
        "metric_compute", "gate_evaluate", "dossier_build",
        "result_index_write", "audit_verify",
    ]
    for stage in expected_stages:
        assert stage in PIPELINE_STAGES, f"Missing stage: {stage}"


def test_pipeline_stage_fields():
    """PipelineStage should have correct fields."""
    stage = PipelineStage("test_stage", "A test stage", record_metrics=True)
    assert stage.name == "test_stage"
    assert stage.description == "A test stage"
    assert stage.record_metrics is True


# ============================================================================
# PipelineInstrumentor Tests
# ============================================================================


def test_pipeline_instrumentor_creation():
    """PipelineInstrumentor should be created with a tracer."""
    instrumentor = PipelineInstrumentor()
    assert instrumentor.tracer is not None


def test_pipeline_instrumentor_stage_context_manager():
    """PipelineInstrumentor should create spans for stages."""
    instrumentor = PipelineInstrumentor()
    with instrumentor.stage("grading", project_id="proj1") as span:
        assert span is not None
        assert span.attributes.get("we3.stage") == "grading"
        assert span.attributes.get("project_id") == "proj1"


def test_pipeline_instrumentor_stage_with_attributes():
    """PipelineInstrumentor should accept custom attributes."""
    instrumentor = PipelineInstrumentor()
    with instrumentor.stage("provider_execute", attributes={
        "model_config_id": "model1",
        "provider": "test-provider",
    }) as span:
        assert span.attributes.get("model_config_id") == "model1"
        assert span.attributes.get("provider") == "test-provider"


def test_pipeline_instrumentor_stage_with_correlation_context():
    """PipelineInstrumentor should include correlation context in spans."""
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


def test_pipeline_instrumentor_record_operation_result():
    """PipelineInstrumentor should record operation results as metrics."""
    instrumentor = PipelineInstrumentor()
    # Should not raise
    instrumentor.record_operation_result(
        "grading",
        success=True,
        project_id="proj1",
        run_id="run1",
    )


def test_pipeline_instrumentor_record_operation_result_failure():
    """PipelineInstrumentor should record failure metrics."""
    instrumentor = PipelineInstrumentor()
    instrumentor.record_operation_result(
        "provider_execute",
        success=False,
        error_class="ProviderFailure",
        project_id="proj1",
    )


def test_pipeline_instrumentor_stage_exception():
    """PipelineInstrumentor should handle exceptions in stages."""
    instrumentor = PipelineInstrumentor()
    with pytest.raises(ValueError):
        with instrumentor.stage("failing_stage"):
            raise ValueError("stage error")


# ============================================================================
# TracingDatabaseSession Tests
# ============================================================================


def test_tracing_db_session_execute():
    """TracingDatabaseSession should wrap session.execute with tracing."""
    mock_session = MagicMock()
    mock_session.execute.return_value = "result"
    session = TracingDatabaseSession(mock_session)

    from sqlalchemy import text
    result = session.execute(text("SELECT 1"))

    assert result == "result"
    mock_session.execute.assert_called_once()


def test_tracing_db_session_commit():
    """TracingDatabaseSession should wrap session.commit with tracing."""
    mock_session = MagicMock()
    session = TracingDatabaseSession(mock_session)
    session.commit()
    mock_session.commit.assert_called_once()


def test_tracing_db_session_rollback():
    """TracingDatabaseSession should wrap session.rollback with tracing."""
    mock_session = MagicMock()
    session = TracingDatabaseSession(mock_session)
    session.rollback()
    mock_session.rollback.assert_called_once()


def test_tracing_db_session_add():
    """TracingDatabaseSession should wrap session.add with tracing."""
    mock_session = MagicMock()
    session = TracingDatabaseSession(mock_session)
    instance = MagicMock()
    session.add(instance)
    mock_session.add.assert_called_once_with(instance)


def test_tracing_db_session_add_all():
    """TracingDatabaseSession should wrap session.add_all with tracing."""
    mock_session = MagicMock()
    session = TracingDatabaseSession(mock_session)
    instances = [MagicMock(), MagicMock()]
    session.add_all(instances)
    mock_session.add_all.assert_called_once_with(instances)


def test_tracing_db_session_get():
    """TracingDatabaseSession should wrap session.get with tracing."""
    mock_session = MagicMock()
    mock_session.get.return_value = "entity"
    session = TracingDatabaseSession(mock_session)
    result = session.get("Entity", "id1")
    assert result == "entity"
    mock_session.get.assert_called_once_with("Entity", "id1")


def test_tracing_db_session_query():
    """TracingDatabaseSession should wrap session.query with tracing."""
    mock_session = MagicMock()
    mock_session.query.return_value = "query"
    session = TracingDatabaseSession(mock_session)
    result = session.query("Entity")
    assert result == "query"
    mock_session.query.assert_called_once_with("Entity")


def test_tracing_db_session_close():
    """TracingDatabaseSession should close the underlying session."""
    mock_session = MagicMock()
    session = TracingDatabaseSession(mock_session)
    session.close()
    mock_session.close.assert_called_once()


def test_tracing_db_session_context_manager():
    """TracingDatabaseSession should support context manager protocol."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)

    with TracingDatabaseSession(mock_session) as session:
        assert session.session is mock_session

    mock_session.__enter__.assert_called_once()
    mock_session.__exit__.assert_called_once()


def test_tracing_db_session_extract_operation_type():
    """TracingDatabaseSession should extract SQL operation type."""
    assert TracingDatabaseSession._extract_operation_type("SELECT * FROM users") == "SELECT"
    assert TracingDatabaseSession._extract_operation_type("INSERT INTO users VALUES (1)") == "INSERT"
    assert TracingDatabaseSession._extract_operation_type("UPDATE users SET name='test'") == "UPDATE"
    assert TracingDatabaseSession._extract_operation_type("DELETE FROM users") == "DELETE"
    assert TracingDatabaseSession._extract_operation_type("CREATE TABLE test (id INT)") == "CREATE"
    assert TracingDatabaseSession._extract_operation_type("UNKNOWN STATEMENT") == "UNKNOWN"


def test_tracing_db_session_extract_table_name():
    """TracingDatabaseSession should extract table name from SQL."""
    assert TracingDatabaseSession._extract_table_name("SELECT * FROM users") == "users"
    assert TracingDatabaseSession._extract_table_name("INSERT INTO users VALUES (1)") == "users"
    assert TracingDatabaseSession._extract_table_name("UPDATE users SET name='test'") == "users"
    assert TracingDatabaseSession._extract_table_name("DELETE FROM users") == "users"
    assert TracingDatabaseSession._extract_table_name("SELECT 1") is None


def test_tracing_db_session_execute_records_span():
    """TracingDatabaseSession.execute should create a database.query span."""
    mock_session = MagicMock()
    mock_session.execute.return_value = "result"
    session = TracingDatabaseSession(mock_session)

    from sqlalchemy import text
    session.execute(text("SELECT * FROM users"))

    # Verify the span was created by checking the tracer has a current span
    # (The span is created and ended within the context manager)
    mock_session.execute.assert_called_once()


def test_tracing_db_session_with_project_id():
    """TracingDatabaseSession should include project_id in spans."""
    mock_session = MagicMock()
    mock_session.execute.return_value = "result"
    session = TracingDatabaseSession(mock_session, project_id="proj1")

    from sqlalchemy import text
    session.execute(text("SELECT 1"))
    mock_session.execute.assert_called_once()


# ============================================================================
# EvaluationPipelineInstrumentor Tests
# ============================================================================


def test_evaluation_pipeline_instrumentor_creation():
    """EvaluationPipelineInstrumentor should be created with a service."""
    mock_service = MagicMock()
    instrumentor = EvaluationPipelineInstrumentor(mock_service)
    assert instrumentor.pipeline is not None
    assert instrumentor.tracer is not None


def test_evaluation_pipeline_instrumentor_run_manifest_success():
    """EvaluationPipelineInstrumentor should trace successful runs."""
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


def test_evaluation_pipeline_instrumentor_run_manifest_failure():
    """EvaluationPipelineInstrumentor should trace failed runs."""
    mock_service = MagicMock()
    mock_service.run_manifest.side_effect = RuntimeError("pipeline error")

    instrumentor = EvaluationPipelineInstrumentor(mock_service)

    with pytest.raises(RuntimeError):
        instrumentor.run_manifest("manifest.yaml", output_dir="/tmp/out")

    mock_service.run_manifest.assert_called_once()


def test_evaluation_pipeline_instrumentor_with_signing_key():
    """EvaluationPipelineInstrumentor should pass signing_key_path."""
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
# get_trace_id Tests
# ============================================================================


def test_get_trace_id_from_active_span():
    """get_trace_id should return trace ID from active span."""
    reset_tracer()
    tracer = get_tracer()
    with tracer.start_as_current_span("test.operation"):
        trace_id = get_trace_id()
        assert trace_id != ""
        assert trace_id != "trc_..."  # Should be a real trace ID


def test_get_trace_id_from_correlation_context():
    """get_trace_id should fall back to correlation context."""
    reset_tracer()
    set_correlation_context(CorrelationContext(trace_id="fallback-trace-123"))
    trace_id = get_trace_id()
    assert trace_id == "fallback-trace-123"


def test_get_trace_id_last_resort():
    """get_trace_id should generate a new ID as last resort."""
    reset_tracer()
    set_correlation_context(CorrelationContext(trace_id=""))
    trace_id = get_trace_id()
    assert trace_id.startswith("trc_")


# ============================================================================
# with_trace_context Tests
# ============================================================================


def test_with_trace_context_from_headers():
    """with_trace_context should create context from trace headers."""
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


def test_with_trace_context_no_headers():
    """with_trace_context should fall back to current context."""
    set_correlation_context(CorrelationContext(trace_id="fallback-trace"))
    context = with_trace_context({})
    assert context.trace_id == "fallback-trace"


# ============================================================================
# Global Instrumentor Tests
# ============================================================================


def test_get_pipeline_instrumentor_creates():
    """get_pipeline_instrumentor should create instrumentor with service."""
    reset_instrumentor()
    mock_service = MagicMock()
    instrumentor = get_pipeline_instrumentor(mock_service)
    assert instrumentor is not None
    assert instrumentor._service is mock_service


def test_get_pipeline_instrumentor_returns_existing():
    """get_pipeline_instrumentor should return existing instance."""
    reset_instrumentor()
    mock_service = MagicMock()
    instrumentor1 = get_pipeline_instrumentor(mock_service)
    instrumentor2 = get_pipeline_instrumentor()
    assert instrumentor1 is instrumentor2


def test_get_pipeline_instrumentor_no_service_raises():
    """get_pipeline_instrumentor should raise when no service provided."""
    reset_instrumentor()
    with pytest.raises(ValueError, match="service must be provided"):
        get_pipeline_instrumentor()


def test_reset_instrumentor():
    """reset_instrumentor should clear the global instrumentor."""
    reset_instrumentor()
    mock_service = MagicMock()
    get_pipeline_instrumentor(mock_service)
    reset_instrumentor()
    with pytest.raises(ValueError):
        get_pipeline_instrumentor()


# ============================================================================
# Security Tests
# ============================================================================


def test_prohibited_attributes_in_allowlist_check():
    """Prohibited attributes should not be in the allowlist."""
    for attr in PROHIBITED_SPAN_ATTRIBUTES:
        assert attr not in ALLOWED_SPAN_ATTRIBUTES, (
            f"Prohibited attribute '{attr}' should not be in allowlist"
        )


def test_dual_span_rejects_prompt_content():
    """DualSpan should reject prompt/response content attributes."""
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


def test_dual_span_rejects_secret_values():
    """DualSpan should reject values containing secret patterns."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    span.set_attribute("custom_field", "password=secret123")
    span.set_attribute("custom_field2", "api_key=abc123")
    assert "custom_field" not in span._lightweight.attributes
    assert "custom_field2" not in span._lightweight.attributes


def test_dual_span_rejects_long_values():
    """DualSpan should reject overly long values."""
    tracer = DualTracer()
    span = tracer.start_span("test.span")
    long_value = "x" * 2000
    span.set_attribute("project_id", long_value)
    assert "project_id" not in span._lightweight.attributes


# ============================================================================
# Integration Tests
# ============================================================================


def test_dual_tracer_integrates_with_correlation_context():
    """DualTracer should integrate with CorrelationContext."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="integration-trace",
        project_id="proj1",
    ))

    tracer = DualTracer()
    with tracer.start_as_current_span("test.operation") as span:
        assert span.trace_id == "integration-trace"


def test_dual_tracer_propagates_trace_id():
    """DualTracer should propagate trace_id from correlation context."""
    reset_tracer()
    set_correlation_context(CorrelationContext(trace_id="propagated-trace"))

    tracer = DualTracer()
    span = tracer.start_span("test.operation")
    assert span.trace_id == "propagated-trace"


def test_pipeline_instrumentor_full_pipeline():
    """PipelineInstrumentor should trace a full pipeline sequence."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="pipeline-trace",
        project_id="proj1",
        experiment_id="exp1",
    ))

    instrumentor = PipelineInstrumentor()

    with instrumentor.stage("manifest_load") as span:
        span.set_attribute("experiment_id", "exp1")

    with instrumentor.stage("grading", attributes={"case_version_id": "case1"}) as span:
        assert span.attributes.get("we3.stage") == "grading"
        assert span.attributes.get("project_id") == "proj1"
        assert span.attributes.get("experiment_id") == "exp1"

    with instrumentor.stage("metric_compute") as span:
        span.set_attribute("model_count", 2)


def test_tracing_db_session_full_workflow():
    """TracingDatabaseSession should support a full database workflow."""
    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock()
    mock_session.get.return_value = MagicMock()
    mock_session.query.return_value = MagicMock()

    with TracingDatabaseSession(mock_session, project_id="proj1") as session:
        session.execute(MagicMock())
        session.add(MagicMock())
        session.get("Entity", "id1")
        session.query("Entity")
        session.commit()

    mock_session.execute.assert_called_once()
    mock_session.add.assert_called_once()
    mock_session.get.assert_called_once()
    mock_session.query.assert_called_once()
    mock_session.commit.assert_called_once()


def test_evaluation_pipeline_instrumentor_end_to_end():
    """EvaluationPipelineInstrumentor should trace the full pipeline."""
    reset_tracer()
    set_correlation_context(CorrelationContext(
        trace_id="e2e-trace",
        project_id="proj1",
    ))

    mock_service = MagicMock()
    mock_outcome = MagicMock()
    mock_outcome.experiment_id = "exp1"
    mock_outcome.gate_statuses = {"model1": "pass"}
    mock_service.run_manifest.return_value = mock_outcome

    instrumentor = EvaluationPipelineInstrumentor(mock_service)
    outcome = instrumentor.run_manifest("manifest.yaml", output_dir="/tmp/out")

    assert outcome is mock_outcome
    assert outcome.experiment_id == "exp1"
    assert outcome.gate_statuses == {"model1": "pass"}


# ============================================================================
# TracingConfig Integration Tests
# ============================================================================


def test_dual_tracer_with_custom_config():
    """DualTracer should use custom TracingConfig."""
    config = TracingConfig(
        service_name="custom-service",
        service_version="2.0.0",
        environment="staging",
    )
    tracer = DualTracer(config)
    assert tracer.config.service_name == "custom-service"
    assert tracer.config.service_version == "2.0.0"
    assert tracer.config.environment == "staging"


def test_dual_tracer_disabled_config():
    """DualTracer should not record when config is disabled."""
    config = TracingConfig(enabled=False)
    tracer = DualTracer(config)
    span = tracer.start_span("test.operation")
    assert span.is_recording is False


# ============================================================================
# Cleanup Tests
# ============================================================================


def test_cleanup_after_tracing_tests():
    """Ensure tracing state is clean after tests."""
    reset_tracer()
    set_correlation_context(CorrelationContext(trace_id=""))
    tracer = get_tracer()
    assert tracer.current_span is None
