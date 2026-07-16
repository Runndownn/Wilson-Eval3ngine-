"""
Failure injection testing infrastructure for persistence and evidence workflows.

T3.1.6 - Deterministic fault controls for PostgreSQL, object storage, and outbox.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger("wilson.failure_injection")


class FaultType(str, Enum):
    """Types of deterministic faults that can be injected."""
    DATABASE_RESTART = "database_restart"
    TRANSACTION_ABORT = "transaction_abort"
    NETWORK_PARTITION = "network_partition"
    OBJECT_STORE_DELAY = "object_store_delay"
    OBJECT_STORE_FAILURE = "object_store_failure"
    PARTIAL_UPLOAD = "partial_upload"
    CONSUMER_OUTAGE = "consumer_outage"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    STALE_LEASE = "stale_lease"
    PROCESS_TERMINATION = "process_termination"


class FaultPhase(str, Enum):
    """Phases where faults can be injected during workflow execution."""
    PRE_OPERATION = "pre_operation"
    DURING_OPERATION = "during_operation"
    POST_OPERATION = "post_operation"
    CLEANUP = "cleanup"


@dataclass
class FaultInjection:
    """A single fault injection point with timing control."""
    fault_type: FaultType
    phase: FaultPhase
    target_ids: list[str] = field(default_factory=list)
    probability: float = 1.0  # 0.0 to 1.0
    delay_seconds: float = 0.0

    def should_inject(self, seed: int | None = None) -> bool:
        """Determine if this fault should be injected based on probability."""
        if seed is not None:
            # Deterministic based on seed
            return (seed % 100) < int(self.probability * 100)
        # In production, would use proper random
        import random
        return random.random() < self.probability


@dataclass
class FaultConfig:
    """Configuration for a complete fault scenario."""
    scenario_id: str
    description: str
    faults: list[FaultInjection] = field(default_factory=list)
    allowlist_targets: list[str] = field(default_factory=list)  # Only inject into these targets
    max_concurrency: int = 1
    timeout_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id is required")


@dataclass
class EvidenceStateSnapshot:
    """Snapshot of evidence state before, during, and after fault scenarios."""
    snapshot_id: str
    scenario_id: str
    captured_at: str
    postgresql_row_count: int = 0
    postgresql_test_row_count: int = 0
    object_store_object_count: int = 0
    outbox_event_count: int = 0
    audit_event_count: int = 0
    object_hashes: list[str] = field(default_factory=list)
    row_hashes: list[str] = field(default_factory=list)
    state_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "scenario_id": self.scenario_id,
            "captured_at": self.captured_at,
            "postgresql_row_count": self.postgresql_row_count,
            "object_store_object_count": self.object_store_object_count,
            "outbox_event_count": self.outbox_event_count,
            "audit_event_count": self.audit_event_count,
        }


class EvidenceAccessor(Protocol):
    """Protocol for accessing evidence state in tests."""

    def count_rows(self, table_name: str) -> int:
        """Count rows in a table."""
        ...

    def count_objects(self) -> int:
        """Count objects in object store."""
        ...

    def count_events(self) -> int:
        """Count outbox events."""
        ...

    def count_audit_events(self) -> int:
        """Count audit events."""
        ...


class ReconciliationReport:
    """Report of reconciliation after fault injection."""

    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        self.before_snapshot: EvidenceStateSnapshot | None = None
        self.after_snapshot: EvidenceStateSnapshot | None = None
        self.inconsistencies: list[dict[str, Any]] = []
        self.quarantined_ids: list[str] = []
        self.resolved_ids: list[str] = []

    # Scheduler reconciliation report attributes
    stranded_jobs: int = 0
    duplicate_logical_keys: int = 0
    orphaned_attempts: int = 0
    lease_violations: int = 0
    details: list[str] = []

    def capture_snapshot(
        self,
        accessor: EvidenceAccessor,
        snapshot_id: str,
        captured_at: str,
    ) -> EvidenceStateSnapshot:
        """Capture current evidence state."""
        snapshot = EvidenceStateSnapshot(
            snapshot_id=snapshot_id,
            scenario_id=self.scenario_id,
            captured_at=captured_at,
            postgresql_row_count=accessor.count_rows("runs"),
            postgresql_test_row_count=accessor.count_rows("classifications"),
            object_store_object_count=accessor.count_objects(),
            outbox_event_count=accessor.count_events(),
            audit_event_count=accessor.count_audit_events(),
        )
        if snapshot_id == "before":
            self.before_snapshot = snapshot
        else:
            self.after_snapshot = snapshot
        return snapshot

    def compute_expected_vs_actual(self) -> list[dict[str, Any]]:
        """Compare before and after snapshots for inconsistencies."""
        if not self.before_snapshot or not self.after_snapshot:
            return []

        inconsistencies = []

        # Check for lost logical runs
        run_diff = self.before_snapshot.postgresql_row_count - self.after_snapshot.postgresql_row_count
        if run_diff > 0:
            inconsistencies.append({
                "type": "lost_runs",
                "expected": self.before_snapshot.postgresql_row_count,
                "actual": self.after_snapshot.postgresql_row_count,
                "missing_count": run_diff,
            })

        # Check for orphaned events
        event_diff = self.after_snapshot.outbox_event_count - self.before_snapshot.outbox_event_count
        if event_diff < 0:
            inconsistencies.append({
                "type": "lost_events",
                "before_count": self.before_snapshot.outbox_event_count,
                "after_count": self.after_snapshot.outbox_event_count,
            })

        self.inconsistencies = inconsistencies
        return inconsistencies

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "inconsistencies": self.inconsistencies,
            "quarantined_ids": self.quarantined_ids,
            "resolved_ids": self.resolved_ids,
            "before_snapshot": self.before_snapshot.to_dict() if self.before_snapshot else None,
            "after_snapshot": self.after_snapshot.to_dict() if self.after_snapshot else None,
        }


class FaultController:
    """
    Controls fault injection during test execution.

    Ensures safe, deterministic, and auditable fault scenarios.
    """

    def __init__(self, config: FaultConfig) -> None:
        self.config = config
        self._active = False
        self._execution_id: str = ""

    def start_scenario(self, execution_id: str) -> None:
        """Begin fault injection scenario."""
        self._active = True
        self._execution_id = execution_id
        logger.info(
            "fault_scenario_started",
            extra={
                "scenario_id": self.config.scenario_id,
                "execution_id": execution_id,
            },
        )

    def stop_scenario(self) -> ReconciliationReport:
        """End fault injection and return reconciliation report."""
        self._active = False
        report = ReconciliationReport(self.config.scenario_id)
        logger.info(
            "fault_scenario_stopped",
            extra={"scenario_id": self.config.scenario_id},
        )
        return report

    def should_inject_fault(
        self,
        fault_type: FaultType,
        target_id: str,
    ) -> bool:
        """Check if a specific fault should be injected for a target."""
        if not self._active:
            return False

        # Check allowlist if configured
        if self.config.allowlist_targets and target_id not in self.config.allowlist_targets:
            return False

        # Check if this fault type is configured
        for fault in self.config.faults:
            if fault.fault_type == fault_type and fault.should_inject():
                return True
        return False

    def assert_safe_target(self, target_id: str) -> None:
        """Assert that target is safe for fault injection (in allowlist)."""
        if self.config.allowlist_targets and target_id not in self.config.allowlist_targets:
            raise ValueError(f"Target {target_id} not in allowlist - fault injection unsafe")


def create_database_restart_scenario() -> FaultConfig:
    """Create a fault scenario for database restart during operation."""
    return FaultConfig(
        scenario_id="db_restart_mid_operation",
        description="Simulate database restart during a write operation",
        faults=[
            FaultInjection(
                fault_type=FaultType.DATABASE_RESTART,
                phase=FaultPhase.DURING_OPERATION,
                probability=1.0,
            ),
        ],
        timeout_seconds=60,
    )


def create_network_partition_scenario() -> FaultConfig:
    """Create a fault scenario for network partition between stores."""
    return FaultConfig(
        scenario_id="network_partition_store_sync",
        description="Simulate network partition between PostgreSQL and object store",
        faults=[
            FaultInjection(
                fault_type=FaultType.NETWORK_PARTITION,
                phase=FaultPhase.DURING_OPERATION,
                delay_seconds=2.0,
            ),
            FaultInjection(
                fault_type=FaultType.OBJECT_STORE_FAILURE,
                phase=FaultPhase.POST_OPERATION,
            ),
        ],
        timeout_seconds=120,
    )


def create_stale_lease_scenario() -> FaultConfig:
    """Create a fault scenario for stale lease during backfill."""
    return FaultConfig(
        scenario_id="stale_lease_backfill",
        description="Simulate stale lease during backfill job processing",
        faults=[
            FaultInjection(
                fault_type=FaultType.STALE_LEASE,
                phase=FaultPhase.DURING_OPERATION,
            ),
        ],
        timeout_seconds=60,
    )


def create_consumer_outage_scenario() -> FaultConfig:
    """Create a fault scenario for outbox consumer outage."""
    return FaultConfig(
        scenario_id="consumer_outage_recovery",
        description="Simulate outbox consumer outage during event processing",
        faults=[
            FaultInjection(
                fault_type=FaultType.CONSUMER_OUTAGE,
                phase=FaultPhase.DURING_OPERATION,
                delay_seconds=5.0,
            ),
            FaultInjection(
                fault_type=FaultType.DUPLICATE_DELIVERY,
                phase=FaultPhase.POST_OPERATION,
            ),
        ],
        timeout_seconds=180,
    )


__all__ = [
    "FaultType",
    "FaultPhase",
    "FaultInjection",
    "FaultConfig",
    "EvidenceStateSnapshot",
    "EvidenceAccessor",
    "ReconciliationReport",
    "FaultController",
    "create_database_restart_scenario",
    "create_network_partition_scenario",
    "create_stale_lease_scenario",
    "create_consumer_outage_scenario",
]