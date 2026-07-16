"""Tests for failure injection testing infrastructure."""

from __future__ import annotations

import pytest

from wilson_eval3ngine.testing.failure_injection import (
    EvidenceStateSnapshot,
    FaultConfig,
    FaultController,
    FaultInjection,
    FaultPhase,
    FaultType,
    ReconciliationReport,
    create_consumer_outage_scenario,
    create_database_restart_scenario,
    create_network_partition_scenario,
    create_stale_lease_scenario,
)


class MockEvidenceAccessor:
    """Mock evidence accessor for testing."""

    def __init__(self) -> None:
        self._rows = 10
        self._objects = 5
        self._events = 8
        self._audit_events = 12

    def count_rows(self, table_name: str) -> int:
        return self._rows

    def count_objects(self) -> int:
        return self._objects

    def count_events(self) -> int:
        return self._events

    def count_audit_events(self) -> int:
        return self._audit_events


class TestFaultInjection:
    """Tests for fault injection configuration."""

    def test_fault_injection_defaults(self):
        """Fault injection has sensible defaults."""
        fault = FaultInjection(
            fault_type=FaultType.DATABASE_RESTART,
            phase=FaultPhase.DURING_OPERATION,
        )
        assert fault.probability == 1.0
        assert fault.delay_seconds == 0.0

    def test_fault_injection_probability(self):
        """Probability-based injection works deterministically."""
        fault = FaultInjection(
            fault_type=FaultType.DATABASE_RESTART,
            phase=FaultPhase.DURING_OPERATION,
            probability=0.5,
        )
        # With seed 49, should inject (49 < 50)
        assert fault.should_inject(seed=49) is True
        # With seed 50, should not inject (50 >= 50)
        assert fault.should_inject(seed=50) is False

    def test_fault_injection_all_types(self):
        """All fault types are defined."""
        assert FaultType.DATABASE_RESTART.value == "database_restart"
        assert FaultType.TRANSACTION_ABORT.value == "transaction_abort"
        assert FaultType.NETWORK_PARTITION.value == "network_partition"
        assert FaultType.OBJECT_STORE_DELAY.value == "object_store_delay"
        assert FaultType.OBJECT_STORE_FAILURE.value == "object_store_failure"
        assert FaultType.PARTIAL_UPLOAD.value == "partial_upload"
        assert FaultType.CONSUMER_OUTAGE.value == "consumer_outage"
        assert FaultType.DUPLICATE_DELIVERY.value == "duplicate_delivery"
        assert FaultType.STALE_LEASE.value == "stale_lease"
        assert FaultType.PROCESS_TERMINATION.value == "process_termination"


class TestFaultConfig:
    """Tests for fault configuration."""

    def test_fault_config_requires_id(self):
        """Fault config requires scenario_id."""
        with pytest.raises(ValueError, match="scenario_id"):
            FaultConfig(scenario_id="", description="test")

    def test_fault_config_defaults(self):
        """Fault config has sensible defaults."""
        config = FaultConfig(
            scenario_id="test_scenario",
            description="A test scenario",
        )
        assert config.max_concurrency == 1
        assert config.timeout_seconds == 300


class TestReconciliationReport:
    """Tests for reconciliation reporting."""

    def test_snapshot_capture(self):
        """Snapshots capture state correctly."""
        report = ReconciliationReport("test_scenario")
        accessor = MockEvidenceAccessor()

        before = report.capture_snapshot(accessor, "before", "2026-01-01T00:00:00Z")
        after = report.capture_snapshot(accessor, "after", "2026-01-01T00:01:00Z")

        assert before.postgresql_row_count == 10
        assert after.postgresql_row_count == 10

    def test_expected_vs_actual_computation(self):
        """Missing runs are detected as inconsistencies."""
        report = ReconciliationReport("test_scenario")
        accessor = MockEvidenceAccessor()

        report.capture_snapshot(accessor, "before", "2026-01-01T00:00:00Z")
        # Simulate lost rows
        accessor._rows = 8
        report.capture_snapshot(accessor, "after", "2026-01-01T00:01:00Z")

        inconsistencies = report.compute_expected_vs_actual()

        assert len(inconsistencies) == 1
        assert inconsistencies[0]["type"] == "lost_runs"

    def test_serialization(self):
        """Report serializes to dict."""
        report = ReconciliationReport("test_scenario")
        accessor = MockEvidenceAccessor()
        report.capture_snapshot(accessor, "before", "2026-01-01T00:00:00Z")

        d = report.to_dict()
        assert d["scenario_id"] == "test_scenario"


class TestFaultController:
    """Tests for fault controller."""

    def test_scenario_lifecycle(self):
        """Scenario can be started and stopped."""
        config = create_database_restart_scenario()
        controller = FaultController(config)

        controller.start_scenario("exec_001")
        assert controller._active is True

        report = controller.stop_scenario()
        assert controller._active is False
        assert report.scenario_id == "db_restart_mid_operation"

    def test_allowlist_enforcement(self):
        """Allowlist is enforced for fault injection."""
        config = FaultConfig(
            scenario_id="allowlist_test",
            description="Test allowlist",
            allowlist_targets=["target_001"],
        )
        controller = FaultController(config)
        controller.start_scenario("exec_002")

        # Target in allowlist
        assert controller.should_inject_fault(FaultType.DATABASE_RESTART, "target_001") is False

        # Target not in allowlist (no matching fault configured)
        assert controller.should_inject_fault(FaultType.DATABASE_RESTART, "target_002") is False

    def test_assert_safe_target(self):
        """Unsafe targets raise assertion error."""
        config = FaultConfig(
            scenario_id="safety_test",
            description="Test safety",
            allowlist_targets=["safe_001"],
        )
        controller = FaultController(config)

        with pytest.raises(ValueError, match="not in allowlist"):
            controller.assert_safe_target("unsafe_002")


class TestScenarioFactories:
    """Tests for fault scenario factory functions."""

    def test_database_restart_scenario(self):
        """Database restart scenario is configured correctly."""
        config = create_database_restart_scenario()
        assert config.scenario_id == "db_restart_mid_operation"
        assert len(config.faults) == 1
        assert config.faults[0].fault_type == FaultType.DATABASE_RESTART

    def test_network_partition_scenario(self):
        """Network partition scenario has multiple faults."""
        config = create_network_partition_scenario()
        assert config.scenario_id == "network_partition_store_sync"
        assert len(config.faults) == 2

    def test_stale_lease_scenario(self):
        """Stale lease scenario is configured correctly."""
        config = create_stale_lease_scenario()
        assert config.scenario_id == "stale_lease_backfill"
        assert config.faults[0].fault_type == FaultType.STALE_LEASE

    def test_consumer_outage_scenario(self):
        """Consumer outage scenario is configured correctly."""
        config = create_consumer_outage_scenario()
        assert config.scenario_id == "consumer_outage_recovery"
        assert config.faults[0].fault_type == FaultType.CONSUMER_OUTAGE
        assert config.faults[1].fault_type == FaultType.DUPLICATE_DELIVERY