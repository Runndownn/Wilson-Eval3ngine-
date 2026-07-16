"""
PostgreSQL queue envelope validation and capacity modeling.

T4.1.1 - Workload profiles and capacity thresholds for PostgreSQL leasing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger("wilson.capacity_model")


class WorkloadProfile(StrEnum):
    """Representative workload profiles for capacity validation."""
    COMMON = "common"  # Normal steady-state operation
    BURST = "burst"  # Flash burst of concurrent jobs
    SLOW_PROVIDER = "slow_provider"  # Provider latency degradation
    PROVIDER_OUTAGE = "provider_outage"  # Full provider failure
    LARGE_OUTPUT = "large_output"  # Oversized artifacts
    REVIEW_BACKLOG = "review_backlog"  # Human review queue saturation
    RECOVERY = "recovery"  # Post-failure catch-up


@dataclass
class CapacityInputs:
    """Versioned capacity model inputs and assumptions."""
    # Job and throughput parameters
    runs_per_hour: int = 100
    jobs_per_run: int = 1
    lease_claims_per_second: float = 5.0
    average_tokens_per_request: int = 1000
    average_tokens_per_response: int = 2000

    # Timing parameters
    average_provider_latency_seconds: float = 2.0
    retry_ratio: float = 0.05
    grading_fanout_factor: int = 1

    # Retention parameters
    retention_days: int = 365
    daily_report_generation: int = 10

    # Concurrency parameters
    max_concurrent_workers: int = 10
    max_concurrent_reports: int = 3

    # Size parameters
    average_artifact_size_bytes: int = 5000
    max_artifact_size_bytes: int = 100000

    # Metadata
    assumptions: list[str] = field(default_factory=lambda: [
        "Linear job distribution across project tenants",
        "Idempotent operations prevent duplicate counting",
        "Reports read latest snapshot, not live data",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs_per_hour": self.runs_per_hour,
            "jobs_per_run": self.jobs_per_run,
            "lease_claims_per_second": self.lease_claims_per_second,
            "average_provider_latency_seconds": self.average_provider_latency_seconds,
            "retry_ratio": self.retry_ratio,
            "grading_fanout_factor": self.grading_fanout_factor,
            "retention_days": self.retention_days,
            "daily_report_generation": self.daily_report_generation,
            "max_concurrent_workers": self.max_concurrent_workers,
            "average_artifact_size_bytes": self.average_artifact_size_bytes,
            "assumptions": self.assumptions,
        }


@dataclass
class CapacityThresholds:
    """Numeric thresholds for PostgreSQL queue envelope validation."""
    # Lease throughput thresholds
    min_lease_claims_per_second: float = 3.0
    target_lease_claims_per_second: float = 10.0

    # Queue depth thresholds
    max_queue_depth_pending: int = 1000
    max_queue_age_seconds: int = 300

    # Database connection thresholds
    max_connection_utilization: float = 0.75

    # Lock wait thresholds
    max_lock_wait_seconds: float = 1.0

    # Report contention thresholds
    max_report_queue_overlap_seconds: int = 60

    # Headroom requirements
    required_headroom_percent: int = 30

    # Migration triggers
    broker_migration_queue_depth: int = 10000
    broker_migration_lock_wait_seconds: float = 5.0


class CapacityModel:
    """
    Validates PostgreSQL queue envelope against workload profiles.

    Computes expected load and compares against measured thresholds.
    """

    def __init__(self, inputs: CapacityInputs | None = None) -> None:
        self.inputs = inputs or CapacityInputs()
        self.thresholds = CapacityThresholds()
        self._validated = False

    def compute_hourly_job_volume(self) -> int:
        """Total jobs expected per hour."""
        return self.inputs.runs_per_hour * self.inputs.jobs_per_run

    def compute_daily_row_growth(self) -> int:
        """Rows added to runs/classifications/metrics tables daily."""
        runs = self.compute_hourly_job_volume() * 24
        classifications = runs * self.inputs.grading_fanout_factor
        metrics = runs
        return runs + classifications + metrics

    def compute_lease_throughput_rps(self) -> float:
        """Lease claims per second (conservative estimate)."""
        base_rps = self.inputs.runs_per_hour / 3600.0
        with_retries = base_rps * (1 + self.inputs.retry_ratio)
        with_fanout = with_retries * self.inputs.grading_fanout_factor
        return with_fanout

    def validate_against_thresholds(self) -> dict[str, Any]:
        """Check capacity model against thresholds."""
        results = {
            "lease_throughput_rps": self.compute_lease_throughput_rps(),
            "lease_throughput_ok": self.compute_lease_throughput_rps() >= self.thresholds.min_lease_claims_per_second,
            "hourly_job_volume": self.compute_hourly_job_volume(),
            "hourly_volume_ok": self.compute_hourly_job_volume() <= self.thresholds.max_queue_depth_pending * 24,
            "daily_growth_estimate": self.compute_daily_row_growth(),
            "threshold_headroom_percent": self.thresholds.required_headroom_percent,
            "migration_triggers": {
                "queue_depth": self.thresholds.broker_migration_queue_depth,
                "lock_wait_seconds": self.thresholds.broker_migration_lock_wait_seconds,
            },
        }
        self._validated = True
        return results

    def requires_broker_migration(self, observed_queue_depth: int, observed_lock_wait: float) -> bool:
        """Determine if broker migration is triggered."""
        return (
            observed_queue_depth >= self.thresholds.broker_migration_queue_depth
            or observed_lock_wait >= self.thresholds.broker_migration_lock_wait_seconds
        )

    def summarize(self) -> str:
        """Generate human-readable capacity summary."""
        v = self.validate_against_thresholds()
        lines = [
            f"Hourly Job Volume: {v['hourly_job_volume']} jobs",
            f"Lease Throughput: {v['lease_throughput_rps']:.2f} claims/sec",
            f"Daily Row Growth: ~{v['daily_growth_estimate']} rows",
            f"Headroom Requirement: {v['threshold_headroom_percent']}%",
        ]
        if v['lease_throughput_ok'] and v['hourly_volume_ok']:
            lines.append("STATUS: Within envelope limits")
        else:
            lines.append("STATUS: Exceeds envelope - review capacity")
        return "\n".join(lines)


@dataclass
class WorkloadScenario:
    """A specific workload scenario for testing."""
    profile: WorkloadProfile
    runs_per_hour: int
    expected_latency_seconds: float
    failure_rate: float = 0.0

    @classmethod
    def from_model(cls, profile: WorkloadProfile, model: CapacityModel) -> "WorkloadScenario":
        """Create scenario from capacity model."""
        base_runs = model.inputs.runs_per_hour
        if profile == WorkloadProfile.BURST:
            runs = base_runs * 10
            latency = model.inputs.average_provider_latency_seconds * 0.5
        elif profile == WorkloadProfile.SLOW_PROVIDER:
            runs = base_runs
            latency = model.inputs.average_provider_latency_seconds * 3
        elif profile == WorkloadProfile.PROVIDER_OUTAGE:
            runs = 0
            latency = 0
            failure_rate = 1.0
        elif profile == WorkloadProfile.LARGE_OUTPUT:
            runs = base_runs
            latency = model.inputs.average_provider_latency_seconds * 2
        elif profile == WorkloadProfile.RECOVERY:
            runs = base_runs * 20
            latency = model.inputs.average_provider_latency_seconds
        else:
            runs = base_runs
            latency = model.inputs.average_provider_latency_seconds

        return cls(
            profile=profile,
            runs_per_hour=runs,
            expected_latency_seconds=latency,
            failure_rate=failure_rate if profile == WorkloadProfile.PROVIDER_OUTAGE else model.inputs.retry_ratio,
        )


__all__ = [
    "CapacityInputs",
    "CapacityModel",
    "CapacityThresholds",
    "WorkloadProfile",
    "WorkloadScenario",
]