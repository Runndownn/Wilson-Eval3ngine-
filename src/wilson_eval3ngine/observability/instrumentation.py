"""
Production observability instrumentation for Wilson Eval3ngine.

This module bridges the lightweight tracer in ``tracing.py`` to the real
OpenTelemetry SDK when available, providing production-grade distributed
tracing with OTLP export. When the SDK is not installed, it gracefully
degrades to the lightweight tracer with no loss of functionality.

Security: Never records prompt/response bodies, secrets, or credentials in
spans. All span attributes are validated against the allowlist defined in
``tracing.ALLOWED_SPAN_ATTRIBUTES``.

Usage:
    from wilson_eval3ngine.observability import (
        setup_opentelemetry,
        instrument_evaluation_pipeline,
        TracingDatabaseSession,
    )

    # Initialize OTel SDK (call once at application startup)
    setup_opentelemetry()

    # Instrument the evaluation service
    instrument_evaluation_pipeline(service)

    # Use tracing-aware database session
    with TracingDatabaseSession(db) as session:
        session.execute(text("SELECT 1"))
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Protocol

from ..tracing import (
    ALLOWED_SPAN_ATTRIBUTES,
    PROHIBITED_SPAN_ATTRIBUTES,
    Span,
    SpanExporter,
    Tracer,
    TracingConfig,
    get_tracer,
    reset_tracer,
)
from ..telemetry import (
    CorrelationContext,
    get_correlation_context,
    set_correlation_context,
)
from ..util import new_id

logger = logging.getLogger("wilson.observability")

# ============================================================================
# OpenTelemetry SDK Detection and Bridge
# ============================================================================

_OTEL_AVAILABLE: bool | None = None
_OTEL_INITIALIZED: bool = False


def is_opentelemetry_available() -> bool:
    """Check if the OpenTelemetry SDK is installed."""
    global _OTEL_AVAILABLE
    if _OTEL_AVAILABLE is None:
        try:
            import opentelemetry  # noqa: F401
            import opentelemetry.sdk  # noqa: F401
            _OTEL_AVAILABLE = True
        except ImportError:
            _OTEL_AVAILABLE = False
    return _OTEL_AVAILABLE


@dataclass(frozen=True, slots=True)
class OTELConfig:
    """Configuration for OpenTelemetry SDK integration."""

    enabled: bool = field(default_factory=lambda: os.getenv("WE3_OTEL_ENABLED", "true").lower() == "true")
    otlp_endpoint: str = field(default_factory=lambda: os.getenv("WE3_OTLP_ENDPOINT", "http://localhost:4317"))
    service_name: str = field(default_factory=lambda: os.getenv("WE3_SERVICE_NAME", "wilson-eval3ngine"))
    service_version: str = field(default_factory=lambda: os.getenv("WE3_SERVICE_VERSION", "0.1.0"))
    environment: str = field(default_factory=lambda: os.getenv("WE3_ENVIRONMENT", "development"))
    traces_sample_rate: float = field(default_factory=lambda: min(1.0, max(0.0, float(os.getenv("WE3_TRACES_SAMPLE_RATE", "1.0")))))
    insecure: bool = field(default_factory=lambda: os.getenv("WE3_OTLP_INSECURE", "true").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("WE3_OTEL_LOG_LEVEL", "INFO"))

    def to_resource_attributes(self) -> dict[str, str]:
        """Convert to OpenTelemetry resource attributes."""
        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
        }


def setup_opentelemetry(config: OTELConfig | None = None) -> bool:
    """Initialize the OpenTelemetry SDK with OTLP export.

    This function is idempotent — calling it multiple times is safe.

    Returns True if the SDK was initialized, False if it's not available
    or disabled.

    Security: Configures the SDK with the same attribute allowlist as the
    lightweight tracer. Propagators are set to W3C TraceContext for
    distributed tracing compatibility.
    """
    global _OTEL_INITIALIZED

    if _OTEL_INITIALIZED:
        return is_opentelemetry_available()

    config = config or OTELConfig()

    if not config.enabled:
        logger.info("opentelemetry_disabled", extra={"reason": "WE3_OTEL_ENABLED=false"})
        return False

    if not is_opentelemetry_available():
        logger.info(
            "opentelemetry_not_available",
            extra={"reason": "opentelemetry-sdk not installed, using lightweight tracer"},
        )
        return False

    try:
        # Import OTel SDK components
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import (
            ALWAYS_ON,
            TraceIdRatioBased,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.propagators.textmap import TraceContextTextMapPropagator
        from opentelemetry.propagators.baggage import BaggagePropagator

        # Create resource with service metadata
        resource = Resource.create(config.to_resource_attributes())

        # Configure sampler
        if config.traces_sample_rate >= 1.0:
            sampler = ALWAYS_ON
        else:
            sampler = TraceIdRatioBased(config.traces_sample_rate)

        # Create tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
            insecure=config.insecure,
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Add console exporter for debugging
        if os.getenv("WE3_OTLP_CONSOLE", "false").lower() == "true":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        # Set global tracer provider
        otel_trace.set_tracer_provider(provider)

        # Configure propagators (W3C TraceContext + Baggage)
        set_global_textmap(CompositePropagator([
            TraceContextTextMapPropagator(),
            BaggagePropagator(),
        ]))

        _OTEL_INITIALIZED = True
        logger.info(
            "opentelemetry_initialized",
            extra={
                "otlp_endpoint": config.otlp_endpoint,
                "service_name": config.service_name,
                "sample_rate": config.traces_sample_rate,
            },
        )
        return True

    except ImportError as e:
        logger.warning(
            "opentelemetry_import_failed",
            extra={"error": str(e)},
        )
        return False
    except Exception as e:
        logger.error(
            "opentelemetry_init_failed",
            extra={"error": str(e)},
        )
        return False


def get_opentelemetry_tracer(name: str = "wilson-eval3ngine") -> Any | None:
    """Get an OpenTelemetry SDK tracer if available.

    Returns None if the SDK is not available or not initialized.
    """
    if not _OTEL_INITIALIZED or not is_opentelemetry_available():
        return None
    try:
        from opentelemetry import trace as otel_trace
        return otel_trace.get_tracer(name)
    except Exception:
        return None


def shutdown_opentelemetry() -> None:
    """Shut down the OpenTelemetry SDK, flushing all pending spans."""
    global _OTEL_INITIALIZED
    if not _OTEL_INITIALIZED:
        return
    try:
        from opentelemetry import trace as otel_trace
        provider = otel_trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
        _OTEL_INITIALIZED = False
    except Exception as e:
        logger.warning("opentelemetry_shutdown_failed", extra={"error": str(e)})


# ============================================================================
# Dual Tracer: Lightweight + OTel SDK
# ============================================================================


@dataclass
class DualTracer:
    """Tracer that emits spans to both the lightweight tracer and OTel SDK.

    When the OTel SDK is available and initialized, spans are emitted to both
    systems. When it's not available, only the lightweight tracer is used.

    Security: All attributes are validated against the allowlist before
    emission to either system.
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        self._config = config or TracingConfig()
        self._lightweight = Tracer(self._config)
        self._otel = get_opentelemetry_tracer(self._config.service_name)

    @property
    def config(self) -> TracingConfig:
        return self._config

    @property
    def lightweight_tracer(self) -> Tracer:
        return self._lightweight

    @property
    def otel_available(self) -> bool:
        return self._otel is not None

    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> "DualSpan":
        """Start a span that emits to both tracers."""
        # Create lightweight span
        lw_span = self._lightweight.start_span(name, attributes=attributes, parent=parent)

        # Create OTel span if available
        otel_span = None
        if self._otel is not None:
            try:
                otel_span = self._otel.start_span(
                    name,
                    attributes={
                        k: v for k, v in (attributes or {}).items()
                        if k in ALLOWED_SPAN_ATTRIBUTES and k.lower() not in PROHIBITED_SPAN_ATTRIBUTES
                    },
                )
            except Exception:
                pass

        return DualSpan(lw_span, otel_span, config=self._config)

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Generator["DualSpan", None, None]:
        """Start a span and set it as current in both tracers."""
        span = self.start_span(name, attributes=attributes, parent=parent)

        # Set as current in lightweight tracer
        previous_lw = self._lightweight._current_span
        self._lightweight._current_span = span._lightweight
        self._lightweight._span_stack.append(span._lightweight)

        # Set as current in OTel tracer using context API
        otel_token = None
        if self._otel is not None and span._otel is not None:
            try:
                from opentelemetry import trace as otel_trace
                from opentelemetry.context import attach, set_value
                # Use the context API to set the span as current
                ctx = otel_trace.set_span_in_context(span._otel)
                otel_token = attach(ctx)
            except Exception:
                pass

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.end()
            # Restore lightweight tracer state
            self._lightweight._span_stack.pop()
            self._lightweight._current_span = previous_lw
            # Detach OTel context
            if otel_token is not None:
                try:
                    from opentelemetry.context import detach
                    detach(otel_token)
                except Exception:
                    pass
            # End OTel span
            if span._otel is not None:
                try:
                    span._otel.end()
                except Exception:
                    pass

    @property
    def current_span(self) -> "DualSpan | None":
        """Get the current span (if any)."""
        lw = self._lightweight.current_span
        if lw is None:
            return None
        return DualSpan(lw, None, config=self._config)

    def inject_trace_context(self, headers: dict[str, str]) -> dict[str, str]:
        """Inject trace context into HTTP headers."""
        # Use lightweight tracer for injection (W3C format)
        result = self._lightweight.inject_trace_context(headers)

        # Also inject via OTel if available
        if self._otel is not None:
            try:
                from opentelemetry import trace as otel_trace
                from opentelemetry.propagators.textmap import DictCarrier
                from opentelemetry.propagate import inject
                # Get the current OTel span context
                current_span = otel_trace.get_current_span()
                if current_span and current_span.is_recording():
                    ctx = otel_trace.set_span_in_context(current_span)
                    carrier = DictCarrier(result)
                    inject(carrier, context=ctx)
                    result.update(carrier)
            except Exception:
                pass

        return result

    def extract_trace_context(self, headers: dict[str, str]) -> dict[str, str] | None:
        """Extract trace context from HTTP headers."""
        return self._lightweight.extract_trace_context(headers)


class DualSpan:
    """Span that emits to both lightweight and OTel tracers."""

    def __init__(
        self,
        lightweight: Span,
        otel: Any | None,
        config: TracingConfig,
    ) -> None:
        self._lightweight = lightweight
        self._otel = otel
        self._config = config

    @property
    def name(self) -> str:
        return self._lightweight.name

    @property
    def trace_id(self) -> str:
        return self._lightweight.trace_id

    @property
    def span_id(self) -> str:
        return self._lightweight.span_id

    @property
    def parent_span_id(self) -> str:
        return self._lightweight.parent_span_id

    @property
    def is_recording(self) -> bool:
        return self._lightweight.is_recording

    @property
    def attributes(self) -> dict[str, Any]:
        """Access the lightweight span's attributes dict."""
        return self._lightweight.attributes

    @property
    def events(self) -> list[dict[str, Any]]:
        """Access the lightweight span's events list."""
        return self._lightweight.events

    def set_attribute(self, key: str, value: Any) -> None:
        """Set attribute on both spans with validation."""
        self._lightweight.set_attribute(key, value)
        if self._otel is not None:
            try:
                key_lower = key.lower()
                if key in ALLOWED_SPAN_ATTRIBUTES and key_lower not in PROHIBITED_SPAN_ATTRIBUTES:
                    self._otel.set_attribute(key, value)
            except Exception:
                pass

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Set multiple attributes on both spans."""
        self._lightweight.set_attributes(attributes)
        if self._otel is not None:
            try:
                safe_attrs = {
                    k: v for k, v in attributes.items()
                    if k in ALLOWED_SPAN_ATTRIBUTES and k.lower() not in PROHIBITED_SPAN_ATTRIBUTES
                }
                self._otel.set_attributes(safe_attrs)
            except Exception:
                pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add event to both spans."""
        self._lightweight.add_event(name, attributes)
        if self._otel is not None:
            try:
                safe_attrs = {
                    k: v for k, v in (attributes or {}).items()
                    if k in ALLOWED_SPAN_ATTRIBUTES and k.lower() not in PROHIBITED_SPAN_ATTRIBUTES
                }
                self._otel.add_event(name, safe_attrs)
            except Exception:
                pass

    def record_exception(self, exception: BaseException) -> None:
        """Record exception on both spans."""
        self._lightweight.record_exception(exception)
        if self._otel is not None:
            try:
                self._otel.record_exception(exception)
            except Exception:
                pass

    def end(self) -> None:
        """End both spans."""
        self._lightweight.end()
        if self._otel is not None:
            try:
                self._otel.end()
            except Exception:
                pass


# ============================================================================
# Pipeline Instrumentation
# ============================================================================


@dataclass
class PipelineStage:
    """Definition of an evaluation pipeline stage for instrumentation."""

    name: str
    description: str
    record_metrics: bool = True


# Standard pipeline stages
PIPELINE_STAGES: dict[str, PipelineStage] = {
    "manifest_load": PipelineStage("manifest_load", "Load experiment manifest"),
    "dataset_load": PipelineStage("dataset_load", "Load dataset manifest"),
    "dataset_validate": PipelineStage("dataset_validate", "Validate dataset reference"),
    "experiment_create": PipelineStage("experiment_create", "Create experiment record"),
    "artifact_store": PipelineStage("artifact_store", "Store manifest and dataset artifacts"),
    "expectation_compile": PipelineStage("expectation_compile", "Compile expectations"),
    "case_iteration": PipelineStage("case_iteration", "Iterate over test cases"),
    "prompt_render": PipelineStage("prompt_render", "Render prompt for case"),
    "provider_execute": PipelineStage("provider_execute", "Execute provider request"),
    "retry_loop": PipelineStage("retry_loop", "Retry provider on failure"),
    "artifact_store_request": PipelineStage("artifact_store_request", "Store request artifact"),
    "artifact_store_response": PipelineStage("artifact_store_response", "Store response artifact"),
    "artifact_store_attempts": PipelineStage("artifact_store_attempts", "Store attempt artifacts"),
    "artifact_store_classification": PipelineStage("artifact_store_classification", "Store classification artifact"),
    "grading": PipelineStage("grading", "Grade response against expectation"),
    "classification_store": PipelineStage("classification_store", "Store classification in database"),
    "metric_compute": PipelineStage("metric_compute", "Compute metrics for model"),
    "metric_store": PipelineStage("metric_store", "Store metric snapshot in database"),
    "gate_evaluate": PipelineStage("gate_evaluate", "Evaluate gates against thresholds"),
    "gate_store": PipelineStage("gate_store", "Store gate decision in database"),
    "audit_append": PipelineStage("audit_append", "Append audit event"),
    "dossier_build": PipelineStage("dossier_build", "Build signed dossier"),
    "dossier_write": PipelineStage("dossier_write", "Write dossier to disk"),
    "result_index_write": PipelineStage("result_index_write", "Write result index"),
    "audit_verify": PipelineStage("audit_verify", "Verify audit chain"),
}


class PipelineInstrumentor:
    """Instrumentor for the evaluation pipeline.

    Wraps the EvaluationService to add tracing spans and metrics recording
    at each pipeline stage, without modifying the service's core logic.

    Security: All span attributes are validated against the allowlist.
    No prompt/response content is ever recorded in spans.
    """

    def __init__(self, tracer: DualTracer | None = None) -> None:
        self._tracer = tracer or DualTracer()
        self._stage_spans: dict[str, DualSpan] = {}

    @property
    def tracer(self) -> DualTracer:
        return self._tracer

    @contextmanager
    def stage(
        self,
        stage_name: str,
        *,
        attributes: dict[str, Any] | None = None,
        project_id: str = "",
        experiment_id: str = "",
        run_id: str = "",
        model_config_id: str = "",
    ) -> Generator[DualSpan, None, None]:
        """Context manager for instrumenting a pipeline stage.

        Records a span for the stage and emits metrics if configured.

        Example:
            with instrumentor.stage("grading", project_id="proj1") as span:
                classification = grader.grade(case, expectation, response)
                span.set_attribute("primary_label", classification.primary_label.value)
        """
        stage = PIPELINE_STAGES.get(stage_name)
        span_name = f"we3.pipeline.{stage_name}"

        # Build attributes from correlation context and parameters
        span_attrs: dict[str, Any] = {"we3.stage": stage_name}
        if attributes:
            span_attrs.update(attributes)

        # Add correlation context
        context = get_correlation_context()
        if context.trace_id:
            span_attrs["trace_id"] = context.trace_id
        if project_id:
            span_attrs["project_id"] = project_id
        elif context.project_id:
            span_attrs["project_id"] = context.project_id
        if experiment_id:
            span_attrs["experiment_id"] = experiment_id
        elif context.experiment_id:
            span_attrs["experiment_id"] = context.experiment_id
        if run_id:
            span_attrs["run_id"] = run_id
        elif context.run_id:
            span_attrs["run_id"] = context.run_id
        if model_config_id:
            span_attrs["model_config_id"] = model_config_id

        start = time.monotonic()
        try:
            with self._tracer.start_as_current_span(span_name, attributes=span_attrs) as span:
                yield span
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            # Record metric if stage is configured for metrics
            if stage and stage.record_metrics:
                try:
                    from ..telemetry import record_metric
                    record_metric(
                        "we3.operation.duration_ms",
                        round(duration_ms, 2),
                        operation=stage_name,
                        project_id=project_id or context.project_id,
                        success=True,
                    )
                except Exception:
                    pass

    def record_operation_result(
        self,
        stage_name: str,
        *,
        success: bool,
        error_class: str | None = None,
        duration_ms: float | None = None,
        project_id: str = "",
        run_id: str = "",
        model_config_id: str = "",
    ) -> None:
        """Record the result of a pipeline operation as a metric."""
        try:
            from ..telemetry import record_metric
            labels: dict[str, Any] = {
                "operation": stage_name,
                "success": success,
            }
            if project_id:
                labels["project_id"] = project_id
            if run_id:
                labels["run_id"] = run_id
            if model_config_id:
                labels["model_config_id"] = model_config_id
            if error_class:
                labels["error_class"] = error_class

            record_metric(
                "we3.operation.duration_ms",
                duration_ms or 0.0,
                **labels,
            )
        except Exception:
            pass


# ============================================================================
# Tracing-Aware Database Session
# ============================================================================


class TracingDatabaseSession:
    """Database session wrapper that records query spans.

    Wraps a SQLAlchemy Session to automatically create spans for each
    database operation (execute, commit, rollback). Spans include the
    SQL operation type and table name (extracted from the query) but
    never include parameter values or query results.

    Security: Only records the operation type and table name, never
    parameter values, query results, or any sensitive data.
    """

    # SQL operation keywords to detect from queries
    _SQL_OPERATIONS = frozenset({
        "SELECT", "INSERT", "UPDATE", "DELETE",
        "CREATE", "ALTER", "DROP", "TRUNCATE",
        "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT",
    })

    def __init__(
        self,
        session: Any,
        tracer: DualTracer | None = None,
        project_id: str = "",
    ) -> None:
        self._session = session
        self._tracer = tracer or DualTracer()
        self._project_id = project_id

    def __enter__(self) -> "TracingDatabaseSession":
        self._session.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self._session.__exit__(*args)

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a SQL statement with tracing."""
        # Extract operation type and table from statement
        op_type = self._extract_operation_type(statement)
        table_name = self._extract_table_name(statement)

        attributes: dict[str, Any] = {
            "db.system": "postgresql" if "postgresql" in str(type(self._session)) else "sqlite",
            "db.operation": op_type,
        }
        if table_name:
            attributes["db.statement"] = f"{op_type} {table_name}"
        if self._project_id:
            attributes["project_id"] = self._project_id

        with self._tracer.start_as_current_span(
            "database.query",
            attributes=attributes,
        ):
            return self._session.execute(statement, *args, **kwargs)

    def commit(self) -> None:
        """Commit the session with tracing."""
        with self._tracer.start_as_current_span("database.commit"):
            self._session.commit()

    def rollback(self) -> None:
        """Rollback the session with tracing."""
        with self._tracer.start_as_current_span("database.rollback"):
            self._session.rollback()

    def add(self, instance: Any) -> None:
        """Add an instance with tracing."""
        with self._tracer.start_as_current_span("database.add"):
            self._session.add(instance)

    def add_all(self, instances: list[Any]) -> None:
        """Add multiple instances with tracing."""
        with self._tracer.start_as_current_span("database.add_all"):
            self._session.add_all(instances)

    def get(self, entity: Any, *args: Any, **kwargs: Any) -> Any:
        """Get an entity by primary key with tracing."""
        with self._tracer.start_as_current_span("database.get"):
            return self._session.get(entity, *args, **kwargs)

    def query(self, *entities: Any, **kwargs: Any) -> Any:
        """Create a query with tracing."""
        with self._tracer.start_as_current_span("database.query_builder"):
            return self._session.query(*entities, **kwargs)

    def begin(self) -> Any:
        """Begin a transaction with tracing."""
        return self._session.begin()

    def close(self) -> None:
        """Close the session."""
        self._session.close()

    @property
    def session(self) -> Any:
        """Access the underlying session."""
        return self._session

    @staticmethod
    def _extract_operation_type(statement: Any) -> str:
        """Extract the SQL operation type from a statement."""
        stmt_str = str(statement).strip().upper()
        for op in TracingDatabaseSession._SQL_OPERATIONS:
            if stmt_str.startswith(op):
                return op
        return "UNKNOWN"

    @staticmethod
    def _extract_table_name(statement: Any) -> str | None:
        """Extract the table name from a SQL statement.

        Security: Only extracts the table name, never parameter values
        or query results.
        """
        stmt_str = str(statement)
        # Simple heuristic: look for table name after FROM, INTO, UPDATE, etc.
        for keyword in ("FROM ", "INTO ", "UPDATE ", "TABLE "):
            idx = stmt_str.upper().find(keyword)
            if idx >= 0:
                remainder = stmt_str[idx + len(keyword):].strip()
                # Extract first identifier
                parts = remainder.split()
                if parts:
                    table = parts[0].strip('"').strip("'")
                    # Filter out SQL keywords
                    if table.upper() not in TracingDatabaseSession._SQL_OPERATIONS:
                        return table
        return None


# ============================================================================
# Evaluation Pipeline Instrumentation
# ============================================================================


class EvaluationPipelineInstrumentor:
    """High-level instrumentor for the EvaluationService.

    Wraps an EvaluationService instance to add tracing spans and metrics
    at each pipeline stage. The wrapped service's behavior is unchanged;
    this class only adds observability.

    Usage:
        service = EvaluationService(database_url="sqlite://", artifact_root="/tmp")
        instrumentor = EvaluationPipelineInstrumentor(service)
        outcome = instrumentor.run_manifest(path, output_dir="/tmp/out")
    """

    def __init__(
        self,
        service: Any,
        tracer: DualTracer | None = None,
    ) -> None:
        self._service = service
        self._tracer = tracer or DualTracer()
        self._pipeline = PipelineInstrumentor(self._tracer)

    @property
    def pipeline(self) -> PipelineInstrumentor:
        return self._pipeline

    @property
    def tracer(self) -> DualTracer:
        return self._tracer

    def run_manifest(
        self,
        manifest_path: str | Any,
        *,
        output_dir: str | Any,
        signing_key_path: str | Any | None = None,
    ) -> Any:
        """Run an experiment with full pipeline instrumentation.

        Wraps EvaluationService.run_manifest() with tracing spans for
        each pipeline stage. The service's behavior is unchanged.
        """
        # Set up correlation context from tracer
        context = get_correlation_context()
        if not context.trace_id:
            context = CorrelationContext(trace_id=new_id("trc"))
            set_correlation_context(context)

        project_id = context.project_id or ""
        experiment_id = context.experiment_id or ""

        # Create top-level span for the entire run
        with self._tracer.start_as_current_span(
            "we3.pipeline.run_manifest",
            attributes={
                "we3.stage": "run_manifest",
                "project_id": project_id,
                "experiment_id": experiment_id,
            },
        ) as run_span:
            try:
                # Call the service's run_manifest method
                # The service internally calls all pipeline stages
                outcome = self._service.run_manifest(
                    manifest_path,
                    output_dir=output_dir,
                    signing_key_path=signing_key_path,
                )

                # Record success
                run_span.set_attribute("status", "success")
                run_span.set_attribute("gate_statuses", str(outcome.gate_statuses))

                # Record metrics
                self._pipeline.record_operation_result(
                    "run_manifest",
                    success=True,
                    project_id=project_id,
                    run_id=str(getattr(outcome, "experiment_id", "")),
                )

                return outcome

            except Exception as exc:
                run_span.record_exception(exc)
                run_span.set_attribute("status", "error")
                run_span.set_attribute("error_class", type(exc).__name__)

                # Record failure metric
                self._pipeline.record_operation_result(
                    "run_manifest",
                    success=False,
                    error_class=type(exc).__name__,
                    project_id=project_id,
                )

                raise


# ============================================================================
# API Endpoint Tracing Helpers
# ============================================================================


def get_trace_id() -> str:
    """Get the current trace ID from the tracing system.

    Replaces the pattern of calling new_id("trc") in API endpoints
    with the actual trace ID from the active span.
    """
    tracer = get_tracer()
    ctx = tracer.get_trace_context()
    if ctx.get("trace_id"):
        return ctx["trace_id"]
    # Fall back to correlation context
    context = get_correlation_context()
    if context.trace_id:
        return context.trace_id
    # Last resort: generate a new one
    return new_id("trc")


def with_trace_context(headers: dict[str, str]) -> CorrelationContext:
    """Create a CorrelationContext from propagated trace headers.

    Used when receiving requests from other services to maintain
    trace continuity across service boundaries.
    """
    from ..tracing import extract_trace_context
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
# Convenience: Global Instrumentor
# ============================================================================

_global_instrumentor: EvaluationPipelineInstrumentor | None = None


def get_pipeline_instrumentor(service: Any | None = None) -> EvaluationPipelineInstrumentor:
    """Get or create the global pipeline instrumentor.

    If a service is provided and no instrumentor exists, creates one.
    If no service is provided and no instrumentor exists, raises ValueError.
    """
    global _global_instrumentor
    if _global_instrumentor is None:
        if service is None:
            raise ValueError("service must be provided to create instrumentor")
        _global_instrumentor = EvaluationPipelineInstrumentor(service)
    return _global_instrumentor


def reset_instrumentor() -> None:
    """Reset the global instrumentor (for testing)."""
    global _global_instrumentor
    _global_instrumentor = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # OTel SDK integration
    "is_opentelemetry_available",
    "OTELConfig",
    "setup_opentelemetry",
    "get_opentelemetry_tracer",
    "shutdown_opentelemetry",
    # Dual tracer
    "DualTracer",
    "DualSpan",
    # Pipeline instrumentation
    "PipelineStage",
    "PIPELINE_STAGES",
    "PipelineInstrumentor",
    "EvaluationPipelineInstrumentor",
    # Database tracing
    "TracingDatabaseSession",
    # API helpers
    "get_trace_id",
    "with_trace_context",
    # Global instrumentor
    "get_pipeline_instrumentor",
    "reset_instrumentor",
]
