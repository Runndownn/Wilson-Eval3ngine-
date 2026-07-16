"""
PostgreSQL leasing benchmarks for queue envelope validation.

T4.1.1 - Benchmark workload profiles against PostgreSQL leasing design.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from wilson_eval3ngine.persistence.database import Database, JobRow
from wilson_eval3ngine.persistence.queue import DurableJobQueue
from wilson_eval3ngine.performance.capacity_model import (
    CapacityModel,
    WorkloadProfile,
    WorkloadScenario,
)


class LeaseBenchmark:
    """Benchmarks PostgreSQL leasing performance under different workloads."""

    def __init__(self, database_url: str) -> None:
        from wilson_eval3ngine.performance.capacity_model import CapacityInputs
        self.database = Database(database_url)
        self.queue = DurableJobQueue(self.database)
        self.model = CapacityModel()

    def setup_test_jobs(
        self,
        count: int,
        project_id: str = "bench_test",
        job_type: str = "benchmark_lease",
    ) -> list[str]:
        """Create test jobs for benchmarking."""
        from wilson_eval3ngine.util import utc_now
        job_ids = []
        with self.database.session() as session, session.begin():
            for i in range(count):
                job_id = f"bench_{uuid.uuid4().hex[:12]}"
                session.add(
                    JobRow(
                        id=job_id,
                        project_id=project_id,
                        job_type=job_type,
                        aggregate_id=f"agg_{i}",
                        state="pending",
                        payload_json={"index": i},
                    )
                )
                job_ids.append(job_id)
        return job_ids

    def measure_lease_performance(
        self,
        job_count: int,
        worker_id: str = "bench_worker",
    ) -> dict[str, Any]:
        """Measure lease throughput and timing."""
        self.setup_test_jobs(job_count)

        start_time = time.monotonic()
        leases_acquired = 0
        lock_waits: list[float] = []

        while True:
            lease_start = time.monotonic()
            lease = self.queue.lease_next(worker_id=worker_id)
            lease_time = time.monotonic() - lease_start

            if lease is None:
                break

            leases_acquired += 1
            lock_waits.append(lease_time)

        total_time = time.monotonic() - start_time
        lease_rps = leases_acquired / total_time if total_time > 0 else 0

        return {
            "jobs_queued": job_count,
            "leases_acquired": leases_acquired,
            "total_time_seconds": round(total_time, 3),
            "lease_rate_per_second": round(lease_rps, 2),
            "avg_lease_latency_ms": round(sum(lock_waits) / len(lock_waits) * 1000, 2) if lock_waits else 0,
            "p95_lease_latency_ms": self._percentile(lock_waits, 95) * 1000,
            "p99_lease_latency_ms": self._percentile(lock_waits, 99) * 1000,
        }

    def _percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * percentile / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def run_workload_benchmark(
        self,
        profile: WorkloadProfile,
    ) -> dict[str, Any]:
        """Run benchmark for specific workload profile."""
        scenario = WorkloadScenario.from_model(profile, self.model)
        jobs_needed = scenario.runs_per_hour

        # Test with 10% of hourly volume for quick benchmark
        test_jobs = max(10, jobs_needed // 10)

        results = self.measure_lease_performance(test_jobs)
        results["profile"] = profile.value
        results["expected_latency_ms"] = scenario.expected_latency_seconds * 1000

        # Validate against thresholds
        thresholds = self.model.thresholds
        results["within_headroom"] = (
            results["lease_rate_per_second"] <= thresholds.target_lease_claims_per_second * 0.7
        )

        return results

    def cleanup(self) -> None:
        """Remove benchmark data."""
        with self.database.session() as session, session.begin():
            session.execute(
                text("DELETE FROM jobs WHERE job_type = 'benchmark_lease'")
            )


# Import text for cleanup
from sqlalchemy import text


def run_all_benchmarks(database_url: str) -> dict[str, Any]:
    """Run benchmarks for all workload profiles."""
    benchmark = LeaseBenchmark(database_url)
    results = {}

    for profile in WorkloadProfile:
        results[profile.value] = benchmark.run_workload_benchmark(profile)

    benchmark.cleanup()
    return results


__all__ = [
    "LeaseBenchmark",
    "run_all_benchmarks",
]