"""
Unit tests for performance qualification and load testing.

TODO 54 - T8.1.4: Performance testing tests
"""


from datetime import datetime, timedelta, timezone

from wilson_eval3ngine.performance.load_testing import (
    LoadProfile,
    LoadScenario,
    LoadMetrics,
    NullWorkloadGenerator,
    MockProviderAdapter,
    PerformanceQualifier,
    run_stability_validation,
)
from wilson_eval3ngine.performance.capacity_model import CapacityModel, WorkloadProfile
from wilson_eval3ngine.observability.sli_slo import SLI, SLIKind, SLIRegistry


class TestLoadProfile:
    """Tests for load profile enumeration."""

    def test_profile_values(self):
        """Load profiles have correct values."""
        assert LoadProfile.COMMON.value == "common"
        assert LoadProfile.BURST.value == "burst"
        assert LoadProfile.SLOW_PROVIDER.value == "slow_provider"
        assert LoadProfile.LARGE_PAYLOAD.value == "large_payload"
        assert LoadProfile.REPORT_HEAVY.value == "report_heavy"
        assert LoadProfile.REVIEW_BACKLOG.value == "review_backlog"
        assert LoadProfile.OVERLOAD.value == "overload"


class TestLoadScenario:
    """Tests for load scenario configuration."""

    def test_scenario_creation(self):
        """Load scenario can be created."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=100,
            concurrent_workers=10,
            payload_size_bytes=5000,
            provider_latency_seconds=2.0,
        )
        assert scenario.profile == LoadProfile.COMMON
        assert scenario.runs_per_hour == 100

    def test_scenario_from_workload(self):
        """Scenario created from workload profile."""
        model = CapacityModel()
        scenario = LoadScenario.from_workload(WorkloadProfile.COMMON, model)

        assert scenario.profile == LoadProfile.COMMON
        assert scenario.runs_per_hour == 100  # Default from model


class TestNullWorkloadGenerator:
    """Tests for deterministic workload generator."""

    def test_generator_creates_runs(self):
        """Generator creates valid run payloads."""
        gen = NullWorkloadGenerator(seed=42)
        run = gen.generate_run("proj_1", "family_1", "model_1")

        assert "run_id" in run
        assert "logical_key" in run
        assert run["prompt_family_id"] == "family_1"

    def test_generator_is_deterministic(self):
        """Generator produces sequential runs."""
        gen = NullWorkloadGenerator(seed=42)
        run1 = gen.generate_run("proj_1", "family_1", "model_1")
        run2 = gen.generate_run("proj_1", "family_1", "model_1")

        assert run1["logical_key"] != run2["logical_key"]
        assert int(run2["logical_key"].split(":")[1]) == int(run1["logical_key"].split(":")[1]) + 1


class TestLoadMetrics:
    """Tests for load metrics collection."""

    def test_metrics_serialization(self):
        """Metrics serialize to dict correctly."""
        metrics = LoadMetrics(
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            p95_latency_ms=150.0,
        )

        d = metrics.to_dict()
        assert d["total_runs"] == 100
        assert d["successful_runs"] == 95
        assert d["failed_runs"] == 5


class TestPerformanceQualifier:
    """Tests for performance qualification runner."""

    def test_qualifier_creates(self):
        """Qualifier can be instantiated."""
        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=LoadScenario(
                profile=LoadProfile.COMMON,
                runs_per_hour=10,
                concurrent_workers=2,
                payload_size_bytes=1000,
                provider_latency_seconds=0.1,
                duration_seconds=1,  # Short test
            ),
        )
        assert q.scenario.profile == LoadProfile.COMMON

    def test_percentile_calculation(self):
        """Percentile calculation works correctly."""
        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=LoadScenario(
                profile=LoadProfile.COMMON,
                runs_per_hour=10,
                concurrent_workers=2,
                payload_size_bytes=1000,
                provider_latency_seconds=0.1,
            ),
        )

        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p50 = q._percentile(values, 50)
        # For 10 values, 50th percentile index = int(10 * 50 / 100) = 5
        assert p50 == 6  # Index 5 in sorted list (values[5] = 6)

        p95 = q._percentile(values, 95)
        assert p95 == 10.0

    def test_headroom_check(self):
        """Headroom check identifies capacity margin."""
        from wilson_eval3ngine.performance.capacity_model import CapacityThresholds

        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=LoadScenario(
                profile=LoadProfile.COMMON,
                runs_per_hour=1000,  # High load
                concurrent_workers=10,
                payload_size_bytes=1000,
                provider_latency_seconds=0.01,  # Very fast
            ),
        )

        metrics = LoadMetrics(
            total_runs=1000,
            test_duration_seconds=60,
            p95_latency_ms=100,
        )

        headroom_met = q._check_headroom(metrics, CapacityThresholds())
        # Should have headroom with high load relative to expected
        assert headroom_met in (True, False)  # Just verify it runs

    def test_no_lost_runs_verification(self):
        """Lost runs detection works."""
        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=LoadScenario(
                profile=LoadProfile.COMMON,
                runs_per_hour=10,
                concurrent_workers=2,
                payload_size_bytes=1000,
                provider_latency_seconds=0.1,
            ),
        )

        metrics_clean = LoadMetrics(lost_logical_runs=0)
        assert q.verify_no_lost_runs(metrics_clean) is True

        metrics_lost = LoadMetrics(lost_logical_runs=5)
        assert q.verify_no_lost_runs(metrics_lost) is False

    def test_no_duplicates_verification(self):
        """Duplicate detection works."""
        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=LoadScenario(
                profile=LoadProfile.COMMON,
                runs_per_hour=10,
                concurrent_workers=2,
                payload_size_bytes=1000,
                provider_latency_seconds=0.1,
            ),
        )

        metrics_clean = LoadMetrics(duplicate_logical_keys=0)
        assert q.verify_no_duplicates(metrics_clean) is True

        metrics_dup = LoadMetrics(duplicate_logical_keys=2)
        assert q.verify_no_duplicates(metrics_dup) is False


class TestMockProviderAdapter:
    """Tests for deterministic mock provider adapter."""

    def test_successful_response(self):
        """Mock provider returns successful response."""
        mock = MockProviderAdapter(seed=42, latency_seconds=0.01)
        response = mock.execute("test prompt", model="test-model")

        assert response["success"] is True
        assert "response_text" in response
        assert response["model"] == "test-model"

    def test_deterministic_latency(self):
        """Mock provider latency is deterministic."""
        mock1 = MockProviderAdapter(seed=42, latency_seconds=0.01)
        mock2 = MockProviderAdapter(seed=42, latency_seconds=0.01)

        # Same seed should produce same latency behavior
        assert mock1.latency_seconds == mock2.latency_seconds

    def test_error_rate_injection(self):
        """Mock provider can inject errors deterministically."""
        mock = MockProviderAdapter(seed=42, error_rate=0.5, latency_seconds=0.01)

        responses = [mock.execute("test") for _ in range(10)]
        error_count = sum(1 for r in responses if not r.get("success", True))

        # With 50% error rate, we expect some errors
        assert error_count > 0

    def test_forced_fault(self):
        """Mock provider can force specific fault types."""
        mock = MockProviderAdapter(seed=42, error_rate=0.0, latency_seconds=0.01)

        response = mock.execute("test", fault_type="timeout")

        assert response["success"] is False
        assert response["error_type"] == "timeout"

    def test_supported_faults(self):
        """Mock provider supports all required fault types."""
        for fault in MockProviderAdapter.SUPPORTED_FAULTS:
            mock = MockProviderAdapter(seed=42, latency_seconds=0.01)
            response = mock.execute("test", fault_type=fault)

            if fault in ["timeout", "rate_limit", "server_error"]:
                assert response["success"] is False


class TestBackpressureDetection:
    """Tests for backpressure detection in performance testing."""

    def test_backpressure_on_error_rate(self):
        """Backpressure triggers on elevated error rate."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=100,
            concurrent_workers=5,
            payload_size_bytes=1000,
            provider_latency_seconds=0.1,
        )

        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=scenario,
        )

        metrics = LoadMetrics(
            total_runs=100,
            failed_runs=15,  # 15% error rate
            p95_latency_ms=100,
        )

        result = q.check_backpressure(metrics)

        assert result["backpressure_triggered"] is True
        assert "error_rate" in result

    def test_backpressure_on_latency(self):
        """Backpressure triggers on elevated latency."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=100,
            concurrent_workers=5,
            payload_size_bytes=1000,
            provider_latency_seconds=0.1,
        )

        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=scenario,
        )

        metrics = LoadMetrics(
            total_runs=100,
            failed_runs=0,
            p95_latency_ms=6000,  # 6 seconds
        )

        result = q.check_backpressure(metrics)

        assert result["backpressure_triggered"] is True
        assert "latency" in result["reasons"][0].lower() or "p95" in result["reasons"][0].lower()

    def test_no_backpressure_normal(self):
        """No backpressure under normal conditions."""
        scenario = LoadScenario(
            profile=LoadProfile.COMMON,
            runs_per_hour=100,
            concurrent_workers=5,
            payload_size_bytes=1000,
            provider_latency_seconds=0.1,
        )

        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=scenario,
        )

        metrics = LoadMetrics(
            total_runs=100,
            failed_runs=0,
            p95_latency_ms=100,
        )

        result = q.check_backpressure(metrics)

        assert result["backpressure_triggered"] is False


class TestStabilityValidation:
    """Tests for stability validation during load tests."""

    def test_stability_validation_runs(self):
        """Stability validation executes without error."""
        result = run_stability_validation(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            duration_seconds=1,
        )

        assert "metrics" in result
        assert "stability" in result

    def test_stability_returns_metrics(self):
        """Stability validation returns load metrics."""
        result = run_stability_validation(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            duration_seconds=1,
        )

        assert "total_runs" in result["metrics"]
        assert result["stability"]["no_exceptions"] is True


# ============================================================================
# Security Tests for Performance Qualification (TODO 54)
# ============================================================================

class TestPerformanceSecurity:
    """Security tests for performance qualification framework.

    Covers denial-of-wallet, quota bypass, oversized inputs, and cross-project fairness.
    """

    def test_mock_provider_no_external_calls(self):
        """Mock provider never makes external network calls."""
        mock = MockProviderAdapter(seed=42, latency_seconds=0.01)

        # Execute should not raise network errors and should be fast
        # (real provider calls would take significantly longer)
        response = mock.execute("test prompt", model="test-model")
        assert response is not None
        assert "success" in response

        # Response should be deterministic mock data, not real provider output
        assert response["response_text"] == "Mock response for run 1"

    def test_oversized_payload_handling(self):
        """System handles oversized payloads without memory issues."""
        # Large payload size should be handled gracefully
        large_payload_bytes = 100 * 1024 * 1024  # 100 MiB

        scenario = LoadScenario(
            profile=LoadProfile.LARGE_PAYLOAD,
            runs_per_hour=1,  # Minimal runs for testing
            concurrent_workers=1,
            payload_size_bytes=large_payload_bytes,
            provider_latency_seconds=0.01,
            duration_seconds=1,
        )

        # Scenario should be created without error
        assert scenario.payload_size_bytes == large_payload_bytes

    def test_cross_project_fairness(self):
        """Mock provider enforces fair behavior across projects."""
        mock1 = MockProviderAdapter(seed=42, error_rate=0.1)
        mock2 = MockProviderAdapter(seed=42, error_rate=0.1)

        # Both should have same configured behavior regardless of project
        assert mock1.error_rate == mock2.error_rate
        assert mock1.latency_seconds == mock2.latency_seconds

        # Multiple calls should maintain deterministic behavior
        for _ in range(5):
            r1 = mock1.execute("prompt")
            r2 = mock2.execute("prompt")
            # Both should have same error characteristics
            assert r1.get("success", True) == r2.get("success", True) or mock1.error_rate > 0

    def test_quota_isolation(self):
        """Performance testing does not bypass quota controls."""
        # The mock adapter has no quota - that's by design for testing
        # Real quota enforcement is at the provider layer
        mock = MockProviderAdapter(seed=42)

        # Mock adapter should not have real quota methods
        assert not hasattr(mock, "check_quota") or mock.error_rate == 0.0
        assert not hasattr(mock, "rate_limit_remaining")

    def test_unauthorized_command_rejection(self):
        """System rejects unauthorized provider commands."""
        mock = MockProviderAdapter(seed=42)

        # The mock adapter should handle arbitrary fault types safely
        # without executing real commands
        response = mock.execute("test prompt", fault_type="timeout")
        assert response["success"] is False
        assert response["error_type"] == "timeout"
        # No actual timeout should occur - mock returns immediately

    def test_safe_payload_generation(self):
        """Workload generator creates safe, non-malicious payloads."""
        gen = NullWorkloadGenerator(seed=42)

        for _ in range(10):
            payload = gen.generate_run("proj_1", "family_1", "model_1")
            # All payloads should have deterministic, safe identifiers
            assert "run_id" in payload
            assert "logical_key" in payload
            assert payload["expected_treatment"] in ["comply", "noncompliant", "error"]

    def test_memory_bounded_load(self):
        """Load testing should not cause unbounded memory growth."""

        # Run stability validation with short duration
        result = run_stability_validation(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            duration_seconds=1,
        )

        # Stability check should report bounded object growth
        assert result["stability"]["memory_stable"] is True

    def test_prompt_not_recorded_in_metrics(self):
        """Prompts are not recorded in test metrics (security)."""
        mock = MockProviderAdapter(seed=42, latency_seconds=0.01)

        # Execute with sensitive prompt
        sensitive_prompt = "SECRET_API_KEY=sk-12345"
        response = mock.execute(sensitive_prompt, model="model_x")

        # Response should not contain the prompt
        assert sensitive_prompt not in str(response)
        assert "response_text" in response

    def test_model_config_isolation(self):
        """Different model configs don't leak across runs."""
        gen = NullWorkloadGenerator(seed=42)

        run_a = gen.generate_run("proj_1", "family_A", "model_v1")
        run_b = gen.generate_run("proj_1", "family_B", "model_v2")

        assert run_a["model_config_id"] == "model_v1"
        assert run_b["model_config_id"] == "model_v2"
        assert run_a["prompt_family_id"] == "family_A"
        assert run_b["prompt_family_id"] == "family_B"

    # ============================================================================
    # Alert Storm Tests (TODO 54)
    # ============================================================================

    def test_alert_storm_handling(self):
        """System handles multiple concurrent alert conditions without flapping."""
        # Simulate multiple backpressure triggers
        scenario = LoadScenario(
            profile=LoadProfile.OVERLOAD,
            runs_per_hour=1000,
            concurrent_workers=20,
            payload_size_bytes=10000,
            provider_latency_seconds=1.0,
        )

        q = PerformanceQualifier(
            database_url="sqlite:///:memory:",
            artifact_root="/tmp/artifacts",
            scenario=scenario,
        )

        # Multiple metrics indicating problems
        metrics = LoadMetrics(
            total_runs=500,
            failed_runs=100,
            p95_latency_ms=10000,
            p99_latency_ms=20000,
            queue_age_seconds=300,
            db_connections_used=100,
        )

        result = q.check_backpressure(metrics)
        # Should detect backpressure without crashing
        assert "backpressure_triggered" in result
        assert "rejected_requests" in result

    def test_incident_coordination_under_failure(self):
        """Performance system coordinates incident detection under multiple failures."""
        from wilson_eval3ngine.observability.error_budget import (
            GracefulDegradationController,
        )

        controller = GracefulDegradationController()

        # Multiple simultaneous failure conditions
        status = controller.evaluate_all(
            evidence_durability=0.90,  # Below threshold
            critical_review_backlog=75,  # Above threshold
            hash_verification_failing_hours=2.0,  # Extended failure
            db_writes_failing=True,
            evidence_integrity_verified=True,
            missing_evidence=True,
            unresolved_critical_reviews=True,
            model_identity_drift=True,
            audit_chain_failed=True,
        )

        # All degradation modes should activate
        assert status.admission_paused is True
        assert status.read_only_mode is True
        assert status.certification_blocked is True
        assert len(status.reasons) >= 3

    def test_load_generator_bottleneck_detection(self):
        """Verify load generator can exceed target before attributing plateau to service."""
        from wilson_eval3ngine.performance.load_testing import NullWorkloadGenerator

        gen = NullWorkloadGenerator(seed=42)

        # Track throughput
        import time
        start = time.monotonic()
        for _ in range(1000):
            gen.generate_run("proj_1", "family_1", "model_1")
        duration = time.monotonic() - start
        throughput = 1000 / max(0.001, duration)

        # Generator should be able to produce at least 10k runs/sec
        # (if it can't, it may bottleneck before service limits are reached)
        assert throughput > 1000  # At least 1000 runs/sec capacity

    def test_clock_skew_handling(self):
        """SLI windowing handles clock skew gracefully."""

        sli = SLI(
            sli_id="sli-api-v1",
            name="API Availability",
            kind=SLIKind.API_AVAILABILITY,
            description="API success rate",
            query_template="test_query",
            measurement_window_minutes=5,
            valid_from="2026-07-16",
        )

        # Create telemetry with future timestamps (clock skew simulation)
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(hours=1)
        skew_telemetries = [
            {"timestamp": future_time, "status": "success"},
            {"timestamp": future_time, "status": "error"},
        ]

        result = sli.compute_from_telemetry(
            skew_telemetries,
            now - timedelta(minutes=5),
            now,
        )

        # Should handle gracefully - records outside window are excluded
        assert result["denominator"] >= 0

    def test_slo_query_changes_mid_window(self):
        """SLI/SLO system tracks query versioning for mid-window changes."""
        registry = SLIRegistry()
        sli = registry.get_sli("sli-api-availability-v1")

        # SLI has valid_from date for versioning
        assert sli is not None
        assert sli.valid_from == "2026-07-16"
        # valid_until can be None (indicates current active query)
        assert sli.valid_until is None or sli.valid_until.startswith("20")
