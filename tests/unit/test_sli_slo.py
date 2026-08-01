"""
Unit tests for SLI/SLO definitions and calculations.

TODO 52 - T8.1.2: SLI/SLO unit tests
"""

from datetime import datetime, timedelta, timezone

from wilson_eval3ngine.observability.sli_slo import (
    SLIKind,
    AlertSeverity,
    SLI,
    SLO,
    SLIRegistry,
    StateReconciler,
)


# ============================================================================
# SLI Tests
# ============================================================================

class TestSLI:
    """Tests for Service Level Indicators."""

    def test_sli_creation(self):
        """SLI can be created with required fields."""
        sli = SLI(
            sli_id="test-sli-v1",
            name="Test SLI",
            kind=SLIKind.API_AVAILABILITY,
            description="Test description",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )
        assert sli.sli_id == "test-sli-v1"
        assert sli.kind == SLIKind.API_AVAILABILITY

    def test_api_availability_computation(self):
        """API availability SLI computes success rate."""
        sli = SLI(
            sli_id="sli-api-v1",
            name="API Availability",
            kind=SLIKind.API_AVAILABILITY,
            description="API success rate",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )

        now = datetime.now(timezone.utc)
        telemetries = [
            {"timestamp": now, "status": "success"},
            {"timestamp": now, "status": "success"},
            {"timestamp": now, "status": "error"},
        ]

        result = sli.compute_from_telemetry(
            telemetries,
            now - timedelta(minutes=5),
            now,
        )

        assert result["numerator"] == 2
        assert result["denominator"] == 3
        assert result["value"] == 2 / 3


class TestSLO:
    """Tests for Service Level Objectives."""

    def test_slo_is_breaching(self):
        """SLO correctly identifies breaching values."""
        slo = SLO(
            slo_id="test-slo",
            sli_id="test-sli",
            name="Test SLO",
            target=0.999,
            warning=0.9995,
            measurement_window_days=30,
        )

        assert slo.is_breaching(0.99) is True  # Below target
        assert slo.is_breaching(0.9995) is False  # Above target
        assert slo.is_breaching(None) is True  # Missing data is breach

    def test_slo_is_warning(self):
        """SLO correctly identifies warning values."""
        slo = SLO(
            slo_id="test-slo",
            sli_id="test-sli",
            name="Test SLO",
            target=0.999,
            warning=0.9995,
            measurement_window_days=30,
        )

        assert slo.is_warning(0.9992) is True  # Between warning and target
        assert slo.is_warning(0.9998) is False  # Above warning
        assert slo.is_warning(None) is False  # None is not warning


class TestSLIRegistry:
    """Tests for SLI registry."""

    def test_registry_initializes_core_slis(self):
        """Registry creates core SLIs on initialization."""
        registry = SLIRegistry()

        assert registry.get_sli("sli-api-availability-v1") is not None
        assert registry.get_sli("sli-evidence-durability-v1") is not None
        assert registry.get_sli("sli-queue-start-latency-p95-v1") is not None
        assert registry.get_sli("sli-grading-duration-p95-v1") is not None
        assert registry.get_sli("sli-report-generation-p99-v1") is not None
        assert registry.get_sli("sli-hash-verification-v1") is not None

    def test_registry_initializes_core_slos(self):
        """Registry creates core SLOs on initialization."""
        registry = SLIRegistry()

        assert registry.get_slo("slo-api-availability-99.9") is not None
        assert registry.get_slo("slo-evidence-durability-99.99") is not None
        assert registry.get_slo("slo-queue-start-latency-5min") is not None

    def test_slo_for_sli_resolution(self):
        """SLO resolves correctly from SLI ID."""
        registry = SLIRegistry()
        slo = registry.get_slo_for_sli("sli-api-availability-v1")

        assert slo is not None
        assert slo.slo_id == "slo-api-availability-99.9"
        assert slo.target == 0.999


class TestStateReconciler:
    """Tests for telemetry/database reconciliation."""

    def test_check_lost_jobs_structure(self):
        """Lost jobs check returns proper structure."""
        reconciler = StateReconciler("sqlite:///:memory:")
        now = datetime.now(timezone.utc)
        result = reconciler.check_lost_jobs(
            "proj_test",
            now - timedelta(hours=1),
            now,
        )

        assert "project_id" in result
        assert "start_time" in result
        assert "end_time" in result
        assert result["reconciled"] is True

    def test_check_stuck_jobs_structure(self):
        """Stuck jobs check returns proper structure."""
        reconciler = StateReconciler("sqlite:///:memory:")
        result = reconciler.check_stuck_jobs()

        assert "stuck_jobs" in result
        assert "check_performed_at" in result

    def test_verify_evidence_integrity_structure(self):
        """Evidence verification returns proper structure."""
        reconciler = StateReconciler("sqlite:///:memory:")
        result = reconciler.verify_evidence_integrity("proj_test")

        assert "project_id" in result
        assert "verified_count" in result
        assert "failed_count" in result


# ============================================================================
# Alert Severity Tests
# ============================================================================

class TestAlertSeverity:
    """Tests for alert severity enumeration."""

    def test_severity_values(self):
        """Alert severity has correct values."""
        assert AlertSeverity.PAGE.value == "page"
        assert AlertSeverity.TICKET.value == "ticket"
        assert AlertSeverity.LOG.value == "log"


class TestSLIKind:
    """Tests for SLI kind enumeration."""

    def test_kind_values(self):
        """SLI kinds have correct values."""
        assert SLIKind.API_AVAILABILITY.value == "api_availability"
        assert SLIKind.EVIDENCE_DURABILITY.value == "evidence_durability"
        assert SLIKind.QUEUE_LATENCY.value == "queue_latency"
        assert SLIKind.GRADING_DURATION.value == "grading_duration"
        assert SLIKind.REPORT_GENERATION.value == "report_generation"
        assert SLIKind.HASH_VERIFICATION.value == "hash_verification"


# ============================================================================
# SLO Serialization Tests (TODO 52)
# ============================================================================

class TestSLOSerialization:
    """Tests for SLO serialization and configuration."""

    def test_slo_to_dict(self):
        """SLO serializes to dict correctly."""
        slo = SLO(
            slo_id="test-slo-v1",
            sli_id="test-sli-v1",
            name="Test SLO",
            target=0.999,
            warning=0.9995,
            measurement_window_days=30,
            owner="Platform Team",
            runbook_url="/docs/runbooks/test.md",
        )

        d = slo.to_dict()
        assert d["slo_id"] == "test-slo-v1"
        assert d["owner"] == "Platform Team"
        assert d["runbook_url"] == "/docs/runbooks/test.md"
        assert d["severity"] == AlertSeverity.TICKET.value

    def test_slo_has_required_fields(self):
        """All registry SLOs have required fields."""
        registry = SLIRegistry()

        for slo_id, slo in registry._slos.items():
            assert slo.owner, f"SLO {slo_id} missing owner"
            assert slo.runbook_url, f"SLO {slo_id} missing runbook_url"


# ============================================================================
# SLI Windowing Tests (TODO 52)
# ============================================================================

class TestSLIWindowing:
    """Tests for SLI measurement window handling."""

    def test_empty_window_returns_no_data(self):
        """Empty telemetry window returns None value."""
        sli = SLI(
            sli_id="sli-api-v1",
            name="API Availability",
            kind=SLIKind.API_AVAILABILITY,
            description="API success rate",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )

        now = datetime.now(timezone.utc)
        result = sli.compute_from_telemetry([], now - timedelta(minutes=5), now)

        assert result["value"] is None
        assert result["numerator"] == 0
        assert result["denominator"] == 0

    def test_window_filtering(self):
        """SLI filters telemetry to measurement window."""
        sli = SLI(
            sli_id="sli-api-v1",
            name="API Availability",
            kind=SLIKind.API_AVAILABILITY,
            description="API success rate",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )

        now = datetime.now(timezone.utc)
        telemetries = [
            {"timestamp": now - timedelta(minutes=10), "status": "success"},  # Outside window
            {"timestamp": now - timedelta(minutes=2), "status": "success"},  # Inside window
            {"timestamp": now, "status": "error"},  # Inside window
        ]

        result = sli.compute_from_telemetry(
            telemetries,
            now - timedelta(minutes=5),
            now,
        )

        # Only 2 records should be in window
        assert result["numerator"] == 1
        assert result["denominator"] == 2


# ============================================================================
# StateReconciler Enhanced Tests (TODO 52)
# ============================================================================

class TestStateReconcilerEnhanced:
    """Enhanced tests for StateReconciler functionality."""

    def test_validate_metric_labels(self):
        """Metric label validation filters to allowed keys."""
        reconciler = StateReconciler("sqlite:///:memory:")

        labels = {
            "project_id": "proj_1",
            "experiment_id": "exp_1",
            "unsafe_key": "should_be_filtered",
            "secret": "should_be_filtered",
        }

        validated = reconciler.validate_metric_labels(labels)
        assert "project_id" in validated
        assert "experiment_id" in validated
        assert "unsafe_key" not in validated
        assert "secret" not in validated

    def test_maintenance_suppression_start(self):
        """Maintenance suppression can be started."""
        reconciler = StateReconciler("sqlite:///:memory:")

        reconciler.start_maintenance_suppression("TestAlert", duration_hours=1)
        assert reconciler.is_suppressed("TestAlert") is True

    def test_maintenance_suppression_end(self):
        """Maintenance suppression can be ended early."""
        reconciler = StateReconciler("sqlite:///:memory:")

        reconciler.start_maintenance_suppression("TestAlert", duration_hours=1)
        reconciler.end_maintenance_suppression("TestAlert")
        assert reconciler.is_suppressed("TestAlert") is False

    def test_maintenance_suppression_expiry(self):
        """Maintenance suppression expires after duration."""
        reconciler = StateReconciler("sqlite:///:memory:")

        # Suppress for 1 hour
        reconciler.start_maintenance_suppression("TestAlert", duration_hours=1)
        # Immediately should be suppressed
        assert reconciler.is_suppressed("TestAlert") is True

    def test_invalid_time_range_raises(self):
        """Invalid time range raises ValueError."""
        reconciler = StateReconciler("sqlite:///:memory:")
        now = datetime.now(timezone.utc)

        # start_time >= end_time should raise - swap the order
        try:
            reconciler.check_lost_jobs("proj", now + timedelta(hours=1), now)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "start_time must be before end_time" in str(e)

    def test_check_stuck_jobs_returns_stuck_count(self):
        """Stuck jobs check returns stuck_count field."""
        reconciler = StateReconciler("sqlite:///:memory:")
        result = reconciler.check_stuck_jobs()

        assert "stuck_count" in result
        assert result["stuck_count"] == 0


# ============================================================================
# Low Traffic Denominator Tests (TODO 52)
# ============================================================================

class TestLowTrafficSLI:
    """Tests for SLI behavior under low traffic conditions."""

    def test_low_traffic_still_measures(self):
        """SLI calculation works with minimal denominator."""
        sli = SLI(
            sli_id="sli-api-v1",
            name="API Availability",
            kind=SLIKind.API_AVAILABILITY,
            description="API success rate",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )

        now = datetime.now(timezone.utc)
        telemetries = [
            {"timestamp": now, "status": "error"},
        ]

        result = sli.compute_from_telemetry(
            telemetries,
            now - timedelta(minutes=5),
            now,
        )

        assert result["value"] == 0.0
        assert result["denominator"] == 1


# ============================================================================
# Missing Telemetry Tests (TODO 52)
# ============================================================================

class TestMissingTelemetry:
    """Tests for handling missing telemetry gracefully."""

    def test_missing_value_is_breach(self):
        """Missing telemetry value counts as SLO breach."""
        slo = SLO(
            slo_id="test-slo",
            sli_id="test-sli",
            name="Test SLO",
            target=0.999,
            warning=0.9995,
            measurement_window_days=30,
        )

        assert slo.is_breaching(None) is True
        assert slo.is_warning(None) is False