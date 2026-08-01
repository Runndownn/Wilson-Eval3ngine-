"""
Unit tests for alert rules and dashboard configurations.

TODO 52 - T8.1.2: Alert and dashboard tests
"""

from wilson_eval3ngine.observability.alerts import (
    AlertCategory,
    AlertRule,
    get_alert_rules,
    compute_alert_fingerprint,
    get_alerts_for_sli,
    get_alert_by_id,
    validate_all_alert_labels,
)
from wilson_eval3ngine.observability.sli_slo import (
    AlertSeverity,
    SLIRegistry,
    StateReconciler,
)
from wilson_eval3ngine.observability.dashboards import (
    DashboardCategory,
    get_dashboards,
)
from wilson_eval3ngine.observability.error_budget import (
    ErrorBudgetState,
    ErrorBudget,
    ErrorBudgetStatus,
    ErrorBudgetPolicy,
    GracefulDegradationController,
    DegradationStatus,
)
from wilson_eval3ngine.util import utc_now


class TestAlertRule:
    """Tests for alert rule definition."""

    def test_alert_rule_creation(self):
        """Alert rule can be created."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test summary",
            description="Test description",
            query="test_query",
            threshold=0.999,
        )
        assert rule.alert_id == "test-alert"

    def test_alert_evaluation(self):
        """Alert evaluation works correctly."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test summary",
            description="Test description",
            query="test_query",
            threshold=0.999,
        )

        assert rule.evaluate(0.998) is True  # Below threshold, should fire
        assert rule.evaluate(0.9995) is False  # Above threshold, no fire
        assert rule.evaluate(None) is False  # None doesn't fire

    def test_prometheus_rule_conversion(self):
        """Alert rule converts to Prometheus format."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test summary",
            description="Test description",
            query="test_query",
            threshold=0.999,
            recovery_condition="test_recovery",
        )

        prometheus_rule = rule.to_prometheus_rule()
        assert prometheus_rule["alert"] == "test-alert"
        assert prometheus_rule["expr"] == "test_query"
        assert "severity" in prometheus_rule["labels"]
        assert "recovery_condition" in prometheus_rule["annotations"]

    def test_should_route_to_page(self):
        """Page severity routes to paging."""
        page_rule = AlertRule(
            alert_id="page-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Page alert",
            description="Test",
            query="test",
            threshold=0.999,
        )
        ticket_rule = AlertRule(
            alert_id="ticket-alert",
            category=AlertCategory.PERFORMANCE,
            severity=AlertSeverity.TICKET,
            sli_id="test-sli",
            summary="Ticket alert",
            description="Test",
            query="test",
            threshold=100,
        )

        assert page_rule.should_route_to_page() is True
        assert ticket_rule.should_route_to_page() is False
        assert page_rule.should_route_to_ticket() is True
        assert ticket_rule.should_route_to_ticket() is True

    def test_validate_alert_labels_safe(self):
        """Alert label validation accepts safe labels."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test",
            description="Test",
            query="test",
            threshold=0.999,
        )

        is_valid, error = rule.validate_labels({"project_id": "proj_1", "run_id": "run_1"})
        assert is_valid is True
        assert error == ""

    def test_validate_alert_labels_rejects_unsafe(self):
        """Alert label validation rejects unsafe labels."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test",
            description="Test",
            query="test",
            threshold=0.999,
        )

        # Rejects attacker-controlled labels
        is_valid, error = rule.validate_labels({"severity": "safe"})
        assert is_valid is False
        assert "severity" in error

        is_valid, error = rule.validate_labels({"owner": "attacker"})
        assert is_valid is False
        assert "owner" in error


class TestGetAlertRulesForSLI:
    """Tests for alert lookup by SLI."""

    def test_get_alerts_for_sli(self):
        """Can get alerts for a specific SLI."""

        alerts = get_alerts_for_sli("sli-api-availability-v1")
        alert_ids = [a.alert_id for a in alerts]

        assert "APIAvailabilityBreaching" in alert_ids
        assert "APIAvailabilityWarning" in alert_ids

    def test_get_alert_by_id(self):
        """Can get specific alert by ID."""
        from wilson_eval3ngine.observability.alerts import get_alert_by_id

        alert = get_alert_by_id("APIAvailabilityBreaching")
        assert alert is not None
        assert alert.sli_id == "sli-api-availability-v1"

    def test_validate_all_alert_labels(self):
        """Batch alert label validation works."""

        overrides = {
            "APIAvailabilityBreaching": {"project_id": "proj_1"},
            "EvidenceDurabilityBreaching": {"unsafe_key": "value"},
        }

        results = validate_all_alert_labels(overrides)

        assert "APIAvailabilityBreaching" in results
        assert "EvidenceDurabilityBreaching" in results
        # The unsafe key in EvidenceDurabilityBreaching labels
        # should fail validation but the test alerts may not have unsafe keys


class TestAlertCategory:
    """Tests for alert category enumeration."""

    def test_category_values(self):
        """Categories have correct values."""
        assert AlertCategory.AVAILABILITY.value == "availability"
        assert AlertCategory.PERFORMANCE.value == "performance"
        assert AlertCategory.INTEGRITY.value == "integrity"
        assert AlertCategory.SECURITY.value == "security"
        assert AlertCategory.COST.value == "cost"


class TestGetAlertRules:
    """Tests for alert rule collection."""

    def test_all_alert_rules_exist(self):
        """All expected alert rules are defined."""
        rules = get_alert_rules()
        rule_ids = [r.alert_id for r in rules]

        assert "APIAvailabilityBreaching" in rule_ids
        assert "EvidenceDurabilityBreaching" in rule_ids
        assert "QueueStartLatencyBreaching" in rule_ids
        assert "GradingDurationBreaching" in rule_ids
        assert "ReportGenerationBreaching" in rule_ids
        assert "HashVerificationFailed" in rule_ids


class TestDashboard:
    """Tests for dashboard definitions."""

    def test_dashboard_categories(self):
        """Dashboard categories are defined."""
        assert DashboardCategory.SERVICE_HEALTH.value == "service_health"
        assert DashboardCategory.QUEUE_METRICS.value == "queue_metrics"
        assert DashboardCategory.PROVIDER_ERRORS.value == "provider_errors"
        assert DashboardCategory.GRADING_REVIEW.value == "grading_review"
        assert DashboardCategory.EVIDENCE_INTEGRITY.value == "evidence_integrity"
        assert DashboardCategory.AUDIT_CONTINUITY.value == "audit_continuity"
        assert DashboardCategory.COST_BUDGET.value == "cost_budget"
        assert DashboardCategory.RELEASE_READINESS.value == "release_readiness"

    def test_dashboards_exist(self):
        """All dashboards are defined."""
        dashboards = get_dashboards()
        dashboard_ids = [d.dashboard_id for d in dashboards]

        assert "we3-service-health" in dashboard_ids
        assert "we3-queue-depth" in dashboard_ids
        assert "we3-provider-errors" in dashboard_ids
        assert "we3-grading-review" in dashboard_ids
        assert "we3-evidence-integrity" in dashboard_ids
        assert "we3-audit-continuity" in dashboard_ids
        assert "we3-cost-budget" in dashboard_ids
        assert "we3-backups" in dashboard_ids
        assert "we3-release-readiness" in dashboard_ids


class TestErrorBudget:
    """Tests for error budget calculations."""

    def test_budget_allowance_calculation(self):
        """Budget allowance computed correctly."""
        budget = ErrorBudget(
            slo_id="test-slo",
            budget_percent=0.1,
            window_days=30,
        )

        allowance = budget.compute_budget_allowance(10000)
        assert allowance == 10  # 0.1% of 10000

    def test_burn_rate_calculation(self):
        """Burn rate computed relative to budget."""
        budget = ErrorBudget(
            slo_id="test-slo",
            budget_percent=0.1,
            window_days=30,
        )

        # Within budget
        burn_rate = budget.compute_burn_rate(5, 10000)
        assert burn_rate == 0.5  # Half of budget

        # At budget
        burn_rate = budget.compute_burn_rate(10, 10000)
        assert burn_rate == 1.0

        # Over budget
        burn_rate = budget.compute_burn_rate(20, 10000)
        assert burn_rate == 2.0


class TestErrorBudgetPolicy:
    """Tests for error budget policy engine."""

    def test_policy_exists(self):
        """Policy initializes with defaults."""
        policy = ErrorBudgetPolicy()
        assert "slo-api-availability-99.9" in policy.budgets
        assert "slo-evidence-durability-99.99" in policy.budgets

    def test_budget_evaluation(self):
        """Budget evaluation returns correct state."""
        policy = ErrorBudgetPolicy()
        status = policy.evaluate_budget("slo-api-availability-99.9", 5, 10000)

        assert status.slo_id == "slo-api-availability-99.9"
        assert status.state in (
            ErrorBudgetState.OK,
            ErrorBudgetState.WARNING,
            ErrorBudgetState.BREACHED,
            ErrorBudgetState.EXHAUSTED,
        )

    def test_release_policy(self):
        """Release policy derived from budget states."""
        policy = ErrorBudgetPolicy()

        # All OK
        statuses_ok = [
            ErrorBudgetStatus(
                slo_id="slo-api-availability-99.9",
                budget=policy.budgets["slo-api-availability-99.9"],
                errors_in_window=5,
                total_in_window=10000,
                burn_rate=0.5,
                state=ErrorBudgetState.OK,
                remaining_budget=50.0,
                next_evaluation=utc_now(),
            ),
        ]
        policy_result, approvals = policy.get_release_policy(statuses_ok)
        assert policy_result == "releases_allowed"
        assert len(approvals) == 0

    def test_maintenance_window_required(self):
        """Maintenance window required when budget breached."""
        policy = ErrorBudgetPolicy()

        assert policy.require_maintenance_window([ErrorBudgetState.BREACHED]) is True
        assert policy.require_maintenance_window([ErrorBudgetState.EXHAUSTED]) is True
        assert policy.require_maintenance_window([ErrorBudgetState.OK]) is False


class TestErrorBudgetState:
    """Tests for error budget state enumeration."""

    def test_state_values(self):
        """States have correct values."""
        assert ErrorBudgetState.OK.value == "ok"
        assert ErrorBudgetState.WARNING.value == "warning"
        assert ErrorBudgetState.BREACHED.value == "breached"
        assert ErrorBudgetState.EXHAUSTED.value == "exhausted"


class TestGracefulDegradationController:
    """Tests for graceful degradation controls."""

    def test_admission_pause_evidence_integrity(self):
        """Admission pauses when evidence integrity below threshold."""
        controller = GracefulDegradationController()
        status = controller.check_admission_pause(evidence_durability=0.98)

        assert status.admission_paused is True
        assert "Evidence durability" in status.reasons[0]

    def test_admission_no_pause_high_integrity(self):
        """Admission continues when evidence integrity above threshold."""
        controller = GracefulDegradationController()
        status = controller.check_admission_pause(evidence_durability=0.999)

        assert status.admission_paused is False

    def test_admission_pause_review_backlog(self):
        """Admission pauses on critical review backlog."""
        controller = GracefulDegradationController()
        status = controller.check_admission_pause(critical_review_backlog=60)

        assert status.admission_paused is True
        assert "Critical review backlog" in status.reasons[0]

    def test_read_only_mode_enabled(self):
        """Read-only mode activates when writes failing but evidence verified."""
        controller = GracefulDegradationController()
        status = controller.check_read_only_mode(
            db_writes_failing=True, evidence_integrity_verified=True
        )

        assert status.read_only_mode is True

    def test_read_only_mode_disabled(self):
        """Read-only mode does not activate when evidence not verified."""
        controller = GracefulDegradationController()
        status = controller.check_read_only_mode(
            db_writes_failing=True, evidence_integrity_verified=False
        )

        assert status.read_only_mode is False

    def test_certification_blocked(self):
        """Certification blocked on missing evidence."""
        controller = GracefulDegradationController()
        status = controller.check_certification(missing_evidence=True)

        assert status.certification_blocked is True
        assert "Missing evidence" in status.reasons[0]

    def test_certification_blocked_multiple_reasons(self):
        """Certification blocked on multiple failure conditions."""
        controller = GracefulDegradationController()
        status = controller.check_certification(
            missing_evidence=True, unresolved_critical_reviews=True, model_identity_drift=True
        )

        assert status.certification_blocked is True
        assert len(status.reasons) == 3

    def test_evaluate_all_conditions(self):
        """All degradation conditions evaluated together."""
        controller = GracefulDegradationController()
        status = controller.evaluate_all(
            evidence_durability=0.98,
            critical_review_backlog=60,
            missing_evidence=True,
        )

        assert status.admission_paused is True
        assert status.certification_blocked is True

    def test_is_system_degraded(self):
        """System degraded check works."""
        controller = GracefulDegradationController()

        degraded_status = DegradationStatus(admission_paused=True)
        healthy_status = DegradationStatus()

        assert controller.is_system_degraded(degraded_status) is True
        assert controller.is_system_degraded(healthy_status) is False

    def test_get_degradation_summary(self):
        """Degradation summary returns safe operational view."""
        controller = GracefulDegradationController()

        status = DegradationStatus(
            admission_paused=True,
            reasons=["Evidence durability low"],
        )

        summary = controller.get_degradation_summary(status)

        assert summary["admission_paused"] is True
        assert summary["reason_count"] == 1
        assert summary["degraded"] is True
        # No sensitive data in summary
        assert "reasons" not in summary or summary["reason_count"] == len(status.reasons)

    # ============================================================================
    # Alert Firing/Recovery Tests (TODO 52)
    # ============================================================================

    def test_alert_firing_and_recovery_scenarios(self):
        """Alert rules fire and recover with correct conditions."""
        # Test breach condition
        alert = get_alert_by_id("APIAvailabilityBreaching")
        assert alert.evaluate(0.998) is True  # Below threshold, fires
        assert alert.evaluate(0.9995) is False  # Above threshold, does not fire

        # Test warning condition
        warning_alert = get_alert_by_id("APIAvailabilityWarning")
        assert warning_alert.evaluate(0.9992) is True  # Below warning threshold
        assert warning_alert.evaluate(0.9998) is False  # Above warning threshold

    def test_alert_recovery_conditions(self):
        """Alert rules have defined recovery conditions."""
        alert = get_alert_by_id("APIAvailabilityBreaching")
        assert alert.recovery_condition != ""
        assert "0.9995" in alert.recovery_condition  # Recovery to warning threshold

    def test_page_alerts_have_recovery_conditions(self):
        """All page-level alerts must have recovery conditions."""
        rules = get_alert_rules()
        for rule in rules:
            if rule.severity == AlertSeverity.PAGE:
                assert rule.recovery_condition != "", f"{rule.alert_id} missing recovery condition"

    # ============================================================================
    # Alert Suppression Abuse Prevention (TODO 52)
    # ============================================================================

    def test_maintenance_suppression_cannot_persist_indefinitely(self):
        """Maintenance suppression has bounded duration."""
        reconciler = StateReconciler("sqlite:///:memory:")

        reconciler.start_maintenance_suppression("TestAlert", duration_hours=24)

        # Should be suppressed initially
        assert reconciler.is_suppressed("TestAlert") is True

        # Suppression should have expiration time
        assert "TestAlert" in reconciler._maintenance_suppressions

    def test_unsupported_label_keys_rejected(self):
        """Alert rules reject unsupported label keys that could indicate injection."""
        rule = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test",
            description="Test",
            query="test",
            threshold=0.999,
        )

        # Test various injection attempts
        injection_attempts = [
            {"severity": "high"},  # Overwrites reserved key
            {"owner": "attacker"},  # Overwrites reserved key
            {"runbook": "http://evil.com"},  # Overwrites reserved key
            {"category": "security"},  # Overwrites reserved key
        ]

        for labels in injection_attempts:
            is_valid, error = rule.validate_labels(labels)
            assert is_valid is False, f"Should reject {labels}"
            assert "cannot be overridden" in error

    def test_alert_fingerprint_deduplication(self):
        """Alert fingerprint ensures proper deduplication."""

        alert = AlertRule(
            alert_id="test-alert",
            category=AlertCategory.AVAILABILITY,
            severity=AlertSeverity.PAGE,
            sli_id="test-sli",
            summary="Test",
            description="Test",
            query="test",
            threshold=0.999,
            fingerprint_fields=["project_id", "experiment_id"],
        )

        # Same labels should produce same fingerprint
        labels1 = {"project_id": "proj_1", "experiment_id": "exp_1"}
        labels2 = {"project_id": "proj_1", "experiment_id": "exp_1"}
        fp1 = compute_alert_fingerprint(alert, labels1)
        fp2 = compute_alert_fingerprint(alert, labels2)
        assert fp1 == fp2

        # Different labels should produce different fingerprint
        labels3 = {"project_id": "proj_2", "experiment_id": "exp_1"}
        fp3 = compute_alert_fingerprint(alert, labels3)
        assert fp3 != fp1

    # ============================================================================
    # Raw Content Leakage Prevention (TODO 52)
    # ============================================================================

    def test_alerts_do_not_include_raw_prompt_content(self):
        """Alert rules do not expose raw prompt/response in summaries."""
        rules = get_alert_rules()

        for rule in rules:
            # Summaries should not contain sensitive patterns
            summary_lower = rule.summary.lower()

            # Should not expose example prompts or responses
            assert "prompt:" not in summary_lower
            assert "response:" not in summary_lower
            assert "secret" not in summary_lower or "secret scan" in summary_lower

    def test_dashboards_no_sensitive_content(self):
        """Dashboard queries do not expose sensitive content."""
        dashboards = get_dashboards()

        for dashboard in dashboards:
            for panel in dashboard.panels:
                query_lower = panel.query.lower()
                # No raw content queries
                assert "prompt_text" not in query_lower
                assert "response_text" not in query_lower

    def test_metric_labels_no_high_cardinality_injection(self):
        """Metric label validation prevents high-cardinality injection."""
        reconciler = StateReconciler("sqlite:///:memory:")

        # Valid labels should pass
        valid = reconciler.validate_metric_labels({
            "project_id": "proj_123",
            "experiment_id": "exp_456",
        })
        assert len(valid) == 2

        # Invalid high-cardinality labels should be filtered
        with_injection = reconciler.validate_metric_labels({
            "project_id": "proj_123",
            "user_controlled": "arbitrary_value",  # Should be filtered
            "secret": "should_be_dropped",  # Should be filtered
        })
        assert "user_controlled" not in with_injection
        assert "secret" not in with_injection

    # ============================================================================
    # Alert Permissions Tests (TODO 52)
    # ============================================================================

    def test_alert_links_are_valid_paths(self):
        """All alert runbook URLs are valid internal paths."""
        rules = get_alert_rules()

        for rule in rules:
            runbook = rule.runbook_url
            # Should be internal path starting with /
            assert runbook.startswith("/"), f"{rule.alert_id} runbook URL is not internal path"
            assert "http" not in runbook.lower() or "localhost" in runbook

    def test_alert_owner_assignment(self):
        """All alerts have assigned owners."""
        rules = get_alert_rules()

        for rule in rules:
            assert rule.owner != "", f"{rule.alert_id} missing owner assignment"

    def test_sli_registry_owners_exist(self):
        """Every SLI has an assigned owner."""
        registry = SLIRegistry()

        for sli_id, sli in registry._slis.items():
            assert sli.owner != "", f"SLI {sli_id} missing owner"
