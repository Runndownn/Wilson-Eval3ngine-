"""
Observability module - SLIs, SLOs, alerts, and dashboards.

TODO 52 - T8.1.2: Service Level Indicators and Objectives
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

__all__ = [
    "SLIKind",
    "AlertSeverity",
    "SLI",
    "SLO",
    "SLIResult",
    "SLIRegistry",
    "StateReconciler",
    "get_sli_registry",
    "record_sli_value",
    "AlertCategory",
    "AlertRule",
    "get_alert_rules",
    "compute_alert_fingerprint",
    "get_alerts_for_sli",
    "get_alert_by_id",
    "validate_all_alert_labels",
    "DashboardCategory",
    "DashboardPanel",
    "Dashboard",
    "get_dashboards",
    "ErrorBudgetState",
    "ErrorBudget",
    "ErrorBudgetStatus",
    "ErrorBudgetPolicy",
    "evaluate_all_budgets",
    "GracefulDegradationController",
    "DegradationStatus",
]
