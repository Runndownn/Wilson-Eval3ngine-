"""Tests for capacity modeling and PostgreSQL queue validation."""

from __future__ import annotations


from wilson_eval3ngine.performance.capacity_model import (
    CapacityInputs,
    CapacityModel,
    CapacityThresholds,
    WorkloadProfile,
    WorkloadScenario,
)


class TestCapacityInputs:
    """Tests for capacity input model."""

    def test_default_inputs(self):
        """Default inputs provide sensible baseline."""
        inputs = CapacityInputs()
        assert inputs.runs_per_hour == 100
        assert inputs.jobs_per_run == 1
        assert inputs.max_concurrent_workers == 10

    def test_serialization(self):
        """Inputs serialize to dict."""
        inputs = CapacityInputs()
        d = inputs.to_dict()
        assert d["runs_per_hour"] == 100
        assert len(d["assumptions"]) == 3


class TestCapacityModel:
    """Tests for capacity validation model."""

    def test_hourly_volume_calculation(self):
        """Hourly volume computed correctly."""
        model = CapacityModel()
        assert model.compute_hourly_job_volume() == 100

    def test_daily_growth_calculation(self):
        """Daily growth accounts for grading fanout."""
        model = CapacityModel(CapacityInputs(grading_fanout_factor=2))
        # runs: 100 * 24 = 2400
        # classifications: 2400 * 2 = 4800
        # metrics: 100 * 24 = 2400
        # total: 2400 + 4800 + 2400 = 9600
        assert model.compute_daily_row_growth() == 9600

    def test_lease_throughput(self):
        """Lease throughput accounts for retries and fanout."""
        model = CapacityModel()
        # 100/3600 * 1.05 * 1 = 0.029166...
        rps = model.compute_lease_throughput_rps()
        assert 0.02 < rps < 0.04

    def test_validation_results(self):
        """Validation returns structured results."""
        model = CapacityModel()
        results = model.validate_against_thresholds()
        assert "lease_throughput_rps" in results
        assert "lease_throughput_ok" in results
        assert "migration_triggers" in results

    def test_broker_migration_trigger(self):
        """Migration trigger logic works."""
        model = CapacityModel()
        # Below threshold
        assert model.requires_broker_migration(5000, 2.0) is False
        # At queue depth threshold
        assert model.requires_broker_migration(10000, 2.0) is True
        # At lock wait threshold
        assert model.requires_broker_migration(5000, 5.0) is True

    def test_summary_generation(self):
        """Summary provides readable output."""
        model = CapacityModel()
        summary = model.summarize()
        assert "Hourly Job Volume" in summary
        assert "Lease Throughput" in summary


class TestWorkloadScenario:
    """Tests for workload scenarios."""

    def test_common_profile(self):
        """Common profile uses baseline values."""
        model = CapacityModel()
        scenario = WorkloadScenario.from_model(WorkloadProfile.COMMON, model)
        assert scenario.runs_per_hour == model.inputs.runs_per_hour

    def test_burst_profile(self):
        """Burst profile scales volume up."""
        model = CapacityModel()
        scenario = WorkloadScenario.from_model(WorkloadProfile.BURST, model)
        assert scenario.runs_per_hour == model.inputs.runs_per_hour * 10

    def test_slow_provider_profile(self):
        """Slow provider profile increases latency."""
        model = CapacityModel(CapacityInputs(average_provider_latency_seconds=2.0))
        scenario = WorkloadScenario.from_model(WorkloadProfile.SLOW_PROVIDER, model)
        assert scenario.expected_latency_seconds == 6.0

    def test_provider_outage_profile(self):
        """Provider outage profile stops jobs and sets failure rate."""
        model = CapacityModel()
        scenario = WorkloadScenario.from_model(WorkloadProfile.PROVIDER_OUTAGE, model)
        assert scenario.runs_per_hour == 0
        assert scenario.failure_rate == 1.0

    def test_large_output_profile(self):
        """Large output profile doubles latency."""
        model = CapacityModel(CapacityInputs(average_provider_latency_seconds=2.0))
        scenario = WorkloadScenario.from_model(WorkloadProfile.LARGE_OUTPUT, model)
        assert scenario.expected_latency_seconds == 4.0

    def test_recovery_profile(self):
        """Recovery profile scales volume up for catch-up."""
        model = CapacityModel(CapacityInputs(average_provider_latency_seconds=2.0))
        scenario = WorkloadScenario.from_model(WorkloadProfile.RECOVERY, model)
        assert scenario.runs_per_hour == model.inputs.runs_per_hour * 20


class TestCapacityThresholds:
    """Tests for validation thresholds."""

    def test_default_thresholds(self):
        """Thresholds have sensible defaults."""
        t = CapacityThresholds()
        assert t.min_lease_claims_per_second == 3.0
        assert t.max_queue_depth_pending == 1000
        assert t.required_headroom_percent == 30

    def test_migration_thresholds(self):
        """Migration thresholds defined."""
        t = CapacityThresholds()
        assert t.broker_migration_queue_depth == 10000
        assert t.broker_migration_lock_wait_seconds == 5.0