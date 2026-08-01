"""
Observability module - SLIs, SLOs, alerts, dashboards, and tracing instrumentation.

TODO 52 - T8.1.2: Service Level Indicators and Objectives
T8.1.1: OpenTelemetry-compatible logs, metrics, and traces.
"""

from .sli_slo import (
    SLIKind,
    AlertSeverity,
    SLI,
    SLO,
    SLIResult,
    SLIRegistry,
    StateReconciler,
    get_sli_registry,
    record_sli_value,
)
from .alerts import (
    AlertCategory,
    AlertRule,
    get_alert_rules,
    compute_alert_fingerprint,
    get_alerts_for_sli,
    get_alert_by_id,
    validate_all_alert_labels,
)
from .dashboards import (
    DashboardCategory,
    DashboardPanel,
    Dashboard,
    get_dashboards,
)
from .error_budget import (
    ErrorBudgetState,
    ErrorBudget,
    ErrorBudgetStatus,
    ErrorBudgetPolicy,
    evaluate_all_budgets,
    GracefulDegradationController,
    DegradationStatus,
)
from .instrumentation import (
    is_opentelemetry_available,
    OTELConfig,
    setup_opentelemetry,
    get_opentelemetry_tracer,
    shutdown_opentelemetry,
    DualTracer,
    DualSpan,
    PipelineStage,
    PIPELINE_STAGES,
    PipelineInstrumentor,
    EvaluationPipelineInstrumentor,
    TracingDatabaseSession,
    get_trace_id,
    with_trace_context,
    get_pipeline_instrumentor,
    reset_instrumentor,
)

__all__ = [
    # SLI/SLO
    "SLIKind",
    "AlertSeverity",
    "SLI",
    "SLO",
    "SLIResult",
    "SLIRegistry",
    "StateReconciler",
    "get_sli_registry",
    "record_sli_value",
    # Alerts
    "AlertCategory",
    "AlertRule",
    "get_alert_rules",
    "compute_alert_fingerprint",
    "get_alerts_for_sli",
    "get_alert_by_id",
    "validate_all_alert_labels",
    # Dashboards
    "DashboardCategory",
    "DashboardPanel",
    "Dashboard",
    "get_dashboards",
    # Error Budget
    "ErrorBudgetState",
    "ErrorBudget",
    "ErrorBudgetStatus",
    "ErrorBudgetPolicy",
    "evaluate_all_budgets",
    "GracefulDegradationController",
    "DegradationStatus",
    # Tracing Instrumentation
    "is_opentelemetry_available",
    "OTELConfig",
    "setup_opentelemetry",
    "get_opentelemetry_tracer",
    "shutdown_opentelemetry",
    "DualTracer",
    "DualSpan",
    "PipelineStage",
    "PIPELINE_STAGES",
    "PipelineInstrumentor",
    "EvaluationPipelineInstrumentor",
    "TracingDatabaseSession",
    "get_trace_id",
    "with_trace_context",
    "get_pipeline_instrumentor",
    "reset_instrumentor",
]
