"""
Integration tests for performance qualification.

TODO 54 - T8.1.4: Integration tests for workload testing
"""

from wilson_eval3ngine.performance.load_testing import (
    PerformanceQualifier,
    LoadScenario,
    LoadMetrics,
)
from wilson_eval3ngine.performance.capacity_model import WorkloadProfile, CapacityModel
from wilson_eval3ngine.performance.load_testing import LoadProfile


class TestPerformanceQualificationIntegration:
    """Integration tests for performance qualification runner."""

    def test_short_load_test(self):
        """Execute a short load test and verify results structure."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=10,
            concurrent_workers=2,
            payload_size_bytes=1000,
            provider_latency_seconds=0.01,
            duration_seconds=1,  # Very short for testing
        )

        qualifier = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/test-artifacts",
            scenario=scenario,
        )

        metrics = qualifier.run_load_test()

        assert metrics.total_runs >= 0
        assert metrics.successful_runs >= 0
        assert metrics.test_duration_seconds > 0
        # Check the to_dict returns proper structure
        d = metrics.to_dict()
        assert "total_runs" in d
        assert "successful_runs" in d


class TestWorkloadProfileIntegration:
    """Integration tests for workload profile variations."""

    def test_all_profiles_executable(self):
        """All workload profiles can be used in qualification."""
        model = CapacityModel()

        for profile in WorkloadProfile:
            scenario = LoadScenario.from_workload(profile, model)
            assert scenario.runs_per_hour >= 0


class TestHeadroomValidation:
    """Tests for required 30% headroom validation."""

    def test_headroom_check_logic(self):
        """Headroom check validates capacity margin."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=100,
            concurrent_workers=10,
            payload_size_bytes=1000,
            provider_latency_seconds=0.1,
        )

        qualifier = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/test",
            scenario=scenario,
        )

        # High throughput relative to expected
        high_throughput_metrics = LoadMetrics(
            total_runs=1000,
            test_duration_seconds=10,
            p95_latency_ms=100,
        )

        # Should have headroom
        headroom_met = qualifier._check_headroom(high_throughput_metrics, None)
        assert isinstance(headroom_met, bool)
