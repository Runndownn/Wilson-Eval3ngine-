"""Unit tests for cross-system game day orchestration (TODO 61).

Tests cover:
- Game day orchestration safeguards
- Fault targeting and allowlist enforcement
- Abort controls and criteria
- Timeline capture and evidence preservation
- Success criteria validation
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

import pytest

from wilson_eval3ngine.testing.game_day import (
    FaultCategory,
    GameDayFinding,
    GameDayMetrics,
    GameDayOrchestrator,
    GameDayReport,
    GameDayScenario,
    GameDayTimelineEvent,
    GamePhase,
    compute_timeline_hash,
    generate_failure_matrix_yaml,
)
from wilson_eval3ngine.operations.cadences import OperationsCadenceManager


class MockEvidenceStore:
    """Mock evidence store for testing."""

    def __init__(self) -> None:
        self._evidence: dict[str, Any] = {}

    def get_evidence(self, project_id: str) -> dict[str, Any]:
        return self._evidence.get(project_id, {})

    def verify_integrity(self, evidence_id: str) -> bool:
        return evidence_id in self._evidence

    def record_artifact(self, artifact: dict[str, Any]) -> str:
        artifact_id = f"artifact_{len(self._evidence)}"
        self._evidence[artifact_id] = artifact
        return artifact_id


class MockAlertSystem:
    """Mock alert system for testing."""

    def __init__(self) -> None:
        self._alerts: list[dict[str, Any]] = []

    def fire_alert(self, alert_id: str, severity: str, details: dict[str, Any]) -> None:
        self._alerts.append({"alert_id": alert_id, "severity": severity, "details": details})

    def acknowledge_alert(self, alert_id: str) -> None:
        for a in self._alerts:
            if a["alert_id"] == alert_id:
                a["acknowledged"] = True

    def resolve_alert(self, alert_id: str) -> None:
        for a in self._alerts:
            if a["alert_id"] == alert_id:
                a["resolved"] = True


class TestGameDayOrchestratorInitialization:
    """Tests for orchestrator initialization and security controls."""

    def test_orchestrator_requires_authorization(self) -> None:
        """Orchestrator cannot execute scenarios without authorization."""
        orchestrator = GameDayOrchestrator()

        with pytest.raises(RuntimeError, match="Authorization must be validated"):
            orchestrator.execute_scenario(orchestrator.FAILURE_MATRIX[0], seed=0)

    def test_authorization_validation(self) -> None:
        """Authorization token must follow format."""
        orchestrator = GameDayOrchestrator()

        # Valid authorization token
        assert orchestrator.validate_authorization("gd_auth_test_token") is True
        assert orchestrator._authorization_granted is True

        # Invalid authorization token
        orchestrator._authorization_granted = False
        assert orchestrator.validate_authorization("invalid_token") is False

    def test_safety_observer_required(self) -> None:
        """Safety observer must be present for execution."""
        orchestrator = GameDayOrchestrator()

        orchestrator.validate_authorization("gd_auth_test")
        orchestrator.assert_safety_observer(True)

        assert orchestrator._safety_observer_present is True

    def test_safety_observer_cannot_be_bypassed(self) -> None:
        """Missing safety observer raises error."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_test")

        with pytest.raises(RuntimeError, match="Independent safety observer required"):
            orchestrator.assert_safety_observer(False)

    def test_failure_matrix_has_all_required_categories(self) -> None:
        """Failure matrix covers all required fault categories."""
        orchestrator = GameDayOrchestrator()

        categories = {s.category for s in orchestrator.FAILURE_MATRIX}

        # Verify all required categories present
        assert FaultCategory.COMMON_FLOW in categories
        assert FaultCategory.RARE_CRITICAL in categories
        assert FaultCategory.HOSTILE_INPUT in categories
        assert FaultCategory.PARTIAL_FAILURE in categories
        assert FaultCategory.CONCURRENCY in categories
        assert FaultCategory.REPLAY in categories
        assert FaultCategory.TIMEOUT_RETRY in categories
        assert FaultCategory.NETWORK_PARTITION in categories
        assert FaultCategory.MALFORMED_DATA in categories
        assert FaultCategory.LARGE_PAYLOAD in categories
        assert FaultCategory.VERSION_SKEW in categories
        assert FaultCategory.DEPENDENCY_OUTAGE in categories
        assert FaultCategory.OPERATOR_ERROR in categories
        assert FaultCategory.SECURITY_COMPROMISE in categories

    def test_failure_matrix_minimally_complete(self) -> None:
        """Failure matrix has at least one scenario per category."""
        orchestrator = GameDayOrchestrator()

        category_counts: dict[str, int] = {}
        for s in orchestrator.FAILURE_MATRIX:
            category_counts[s.category.value] = category_counts.get(s.category.value, 0) + 1

        # Each category should have at least one scenario
        for category in FaultCategory:
            assert category_counts.get(category.value, 0) >= 1, f"Missing scenarios for {category}"


class TestGameDayScenarioExecution:
    """Tests for scenario execution and metrics collection."""

    def test_scenario_execution_records_timeline(self) -> None:
        """Scenario execution creates timeline events."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_test")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="test_scenario",
            category=FaultCategory.COMMON_FLOW,
            description="Test scenario",
        )

        metrics, findings = orchestrator.execute_scenario(scenario, seed=42)

        assert len(orchestrator._timeline) > 0
        assert any(e.event_type == "scenario_started" for e in orchestrator._timeline)
        assert any(e.event_type == "scenario_completed" for e in orchestrator._timeline)

    def test_scenario_metrics_populated(self) -> None:
        """Scenario metrics are populated correctly."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_test")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="test_scenario",
            category=FaultCategory.COMMON_FLOW,
            description="Test scenario",
        )

        metrics, findings = orchestrator.execute_scenario(scenario, seed=0)

        assert metrics.mttd_seconds >= 0
        assert metrics.acknowledgment_seconds >= 0
        assert metrics.containment_seconds >= 0
        assert metrics.recovery_seconds >= 0

    def test_rare_critical_scenario_rto_rpo_targets(self) -> None:
        """Rare critical scenarios target RPO=15min, RTO=4hr."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_test")
        orchestrator.assert_safety_observer(True)

        rare_scenario = GameDayScenario(
            scenario_id="rare_test",
            category=FaultCategory.RARE_CRITICAL,
            description="Rare critical test",
        )

        metrics, findings = orchestrator.execute_scenario(rare_scenario, seed=0)

        assert metrics.rpo_minutes == 15.0
        assert metrics.rto_hours == 4.0


class TestAbortControls:
    """Tests for abort criteria and controls."""

    def test_abort_criteria_detection(self) -> None:
        """Abort criteria are properly detected."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_test")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="abort_test",
            category=FaultCategory.RARE_CRITICAL,
            description="Abort test scenario",
            abort_criteria=["data_loss_detected", "integrity_violation"],
        )

        # Test abort detection with matching state
        matched = orchestrator.check_abort_criteria(scenario, {"data_loss_detected": True})
        assert matched == "data_loss_detected"

        # Test abort detection with non-matching state
        matched = orchestrator.check_abort_criteria(scenario, {"other_issue": True})
        assert matched is None

    def test_security_compromise_requires_approval(self) -> None:
        """Security compromise scenarios require author approval."""
        orchestrator = GameDayOrchestrator()

        security_scenario = None
        for s in orchestrator.FAILURE_MATRIX:
            if s.category == FaultCategory.SECURITY_COMPROMISE:
                security_scenario = s
                break

        assert security_scenario is not None
        assert security_scenario.requires_author_approval is True


class TestTimelineCapture:
    """Tests for timeline event capture and evidence preservation."""

    def test_timeline_event_creation(self) -> None:
        """Timeline events are created with correct structure."""
        orchestrator = GameDayOrchestrator()

        event = orchestrator.record_event(
            "test_event",
            GamePhase.DETECTION,
            "tester",
            {"detail": "value"},
            evidence_ref="evidence_001",
        )

        assert event.event_type == "test_event"
        assert event.phase == GamePhase.DETECTION
        assert event.actor == "tester"
        assert event.details == {"detail": "value"}
        assert event.evidence_ref == "evidence_001"

    def test_timeline_serializable(self) -> None:
        """Timeline is serializable for evidence package."""
        orchestrator = GameDayOrchestrator()

        orchestrator.record_event("event1", GamePhase.PREPARATION, "actor1", {})
        orchestrator.record_event("event2", GamePhase.DETECTION, "actor2", {})

        serialized = json.dumps([e.to_dict() for e in orchestrator._timeline])
        assert len(serialized) > 0

        parsed = json.loads(serialized)
        assert len(parsed) == 2

    def test_timeline_deterministic_hash(self) -> None:
        """Timeline produces deterministic hash for verification."""
        events = [
            GameDayTimelineEvent(
                event_type="event1",
                phase=GamePhase.PREPARATION,
                timestamp="2026-01-01T00:00:00Z",
                actor="tester",
                details={},
            ),
            GameDayTimelineEvent(
                event_type="event2",
                phase=GamePhase.DETECTION,
                timestamp="2026-01-01T00:00:01Z",
                actor="tester",
                details={},
            ),
        ]

        hash1 = compute_timeline_hash(events)
        hash2 = compute_timeline_hash(events)

        assert hash1 == hash2
        assert hash1.startswith("sha256:")


class TestSuccessCriteria:
    """Tests for success criteria validation."""

    def test_metrics_threshold_compliance(self) -> None:
        """Metrics comply with tolerance thresholds."""
        metrics = GameDayMetrics(
            mttd_seconds=60.0,  # Should be < 300s
            acknowledgment_seconds=30.0,  # Should be < 60s
            containment_seconds=120.0,  # Should be < 600s
            recovery_seconds=3600.0,  # Should be < 4hr
            reconciliation_seconds=600.0,  # Should be < 1hr
            rpo_minutes=15.0,  # Target is 15min
            rto_hours=4.0,  # Target is 4hr
            data_integrity_verified=True,
            decision_correctness_score=0.95,  # Should be >= 0.9
        )

        assert metrics.mttd_seconds < 300
        assert metrics.acknowledgment_seconds < 60
        assert metrics.containment_seconds < 600
        assert metrics.recovery_seconds < 4 * 3600

    def test_data_integrity_must_be_verified(self) -> None:
        """Data integrity must be verified for successful recovery."""
        metrics_with_integrity = GameDayMetrics(data_integrity_verified=True)
        metrics_without_integrity = GameDayMetrics(data_integrity_verified=False)

        assert metrics_with_integrity.data_integrity_verified is True
        assert metrics_without_integrity.data_integrity_verified is False


class TestGameDayFinding:
    """Tests for game day finding structure."""

    def test_finding_fields(self) -> None:
        """Finding has all required fields."""
        finding = GameDayFinding(
            finding_id="finding_001",
            scenario_id="scenario_001",
            severity="critical",
            description="Test finding",
            owner="SRE Team",
            due_date="2026-07-24",
            containment_applied=True,
            regression_scenario="test_regression",
            certification_impact="blocks_cert",
        )

        assert finding.severity == "critical"
        assert finding.owner == "SRE Team"
        assert finding.containment_applied is True
        assert finding.retest_required is False  # Default

    def test_finding_serialization(self) -> None:
        """Finding serializes correctly for reporting."""
        finding = GameDayFinding(
            finding_id="finding_002",
            scenario_id="scenario_001",
            severity="high",
            description="High severity finding",
            owner="Platform Team",
            due_date="2026-07-24",
            containment_applied=True,
            regression_scenario="regression",
            certification_impact="warning",
        )

        d = finding.to_dict()
        assert d["finding_id"] == "finding_002"
        assert d["severity"] == "high"


class TestGameDayReport:
    """Tests for complete game day report."""

    def test_report_structure(self) -> None:
        """Report has complete structure."""
        report = GameDayReport(
            exercise_id="gd_test_001",
            executed_at=datetime.now(timezone.utc).isoformat(),
            scenarios_executed=["s1", "s2", "s3"],
            timeline=[],
            metrics=GameDayMetrics(),
            findings=[],
        )

        assert report.exercise_id == "gd_test_001"
        assert len(report.scenarios_executed) == 3
        assert report.aborted is False

    def test_report_serialization(self) -> None:
        """Report serializes for storage and analysis."""
        finding = GameDayFinding(
            finding_id="f1",
            scenario_id="s1",
            severity="medium",
            description="Test",
            owner="Team",
            due_date="2026-07-24",
            containment_applied=False,
            regression_scenario="none",
            certification_impact="no_impact",
        )
        report = GameDayReport(
            exercise_id="gd_test_002",
            executed_at=datetime.now(timezone.utc).isoformat(),
            scenarios_executed=["s1"],
            timeline=[],
            metrics=GameDayMetrics(),
            findings=[finding],
        )

        d = report.to_dict()
        assert "exercise_id" in d
        assert "metrics" in d
        assert "findings" in d
        assert len(d["findings"]) == 1


class TestFailureMatrixGeneration:
    """Tests for failure matrix YAML generation."""

    def test_yaml_generation(self) -> None:
        """Failure matrix generates valid YAML."""
        yaml_output = generate_failure_matrix_yaml()

        assert "failure_matrix:" in yaml_output
        assert "gd_common_001" in yaml_output or "category:" in yaml_output


class TestGameDayMetrics:
    """Tests for game day metrics data structure."""

    def test_metrics_serialization(self) -> None:
        """Metrics serialize correctly."""
        metrics = GameDayMetrics(
            mttd_seconds=45.5,
            acknowledgment_seconds=30.0,
            containment_seconds=120.0,
            recovery_seconds=1800.0,
            reconciliation_seconds=600.0,
            rpo_minutes=15.0,
            rto_hours=3.5,
            slo_impact_pct=2.5,
            data_integrity_verified=True,
            decision_correctness_score=0.99,
            communication_timing_minutes=15.0,
        )

        d = metrics.to_dict()
        assert d["mttd_seconds"] == 45.5
        assert d["rpo_minutes"] == 15.0
        assert d["rto_hours"] == 3.5
        assert d["data_integrity_verified"] is True


class TestIntegrationWithExistingSystems:
    """Tests for integration with existing backup, certification, and operations systems."""

    def test_can_integrate_with_operations_manager(self) -> None:
        """Game day can use existing operations manager."""
        operations_manager = OperationsCadenceManager()
        orchestrator = GameDayOrchestrator(operations_manager=operations_manager)

        assert orchestrator.operations_manager is operations_manager

    def test_can_integrate_with_evidence_store(self) -> None:
        """Game day can use external evidence store."""
        evidence_store = MockEvidenceStore()
        orchestrator = GameDayOrchestrator(evidence_accessor=evidence_store)

        assert orchestrator.evidence_accessor is evidence_store

    def test_can_integrate_with_alert_system(self) -> None:
        """Game day can use external alert system."""
        alert_system = MockAlertSystem()
        orchestrator = GameDayOrchestrator(alert_system=alert_system)

        assert orchestrator.alert_system is alert_system


class TestConcurrentExecution:
    """Tests for thread-safe game day execution."""

    def test_timeline_thread_safety(self) -> None:
        """Timeline recording is thread-safe."""
        orchestrator = GameDayOrchestrator()

        def record_events(start_idx: int, count: int) -> None:
            for i in range(start_idx, start_idx + count):
                orchestrator.record_event(
                    f"event_{i}",
                    GamePhase.PREPARATION,
                    f"actor_{i}",
                    {"index": i},
                )

        threads = [
            threading.Thread(target=record_events, args=(i * 100, 100))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(orchestrator._timeline) == 300


class TestEvidencePreservationInFindings:
    """Tests for evidence preservation in security findings."""

    def test_security_finding_evidence_attachments(self) -> None:
        """Security findings can reference evidence artifacts."""
        finding = GameDayFinding(
            finding_id="security_001",
            scenario_id="gd_security_001",
            severity="critical",
            description="Compromised signing key detected",
            owner="Security Team",
            due_date="2026-07-24",
            containment_applied=True,
            regression_scenario="key_rotation",
            certification_impact="blocks_cert",
            evidence_refs=["evidence_audit_001", "evidence_telemetry_001"],
            retest_required=True,
        )

        assert len(finding.evidence_refs) == 2
        assert "evidence_audit_001" in finding.evidence_refs


class TestGameDayScenario:
    """Tests for GameDayScenario dataclass."""

    def test_scenario_serialization(self) -> None:
        """Scenario serializes correctly."""
        scenario = GameDayScenario(
            scenario_id="test_001",
            category=FaultCategory.COMMON_FLOW,
            description="Test scenario",
            fault_configs=[{"type": "test_fault"}],
            abort_criteria=["critical_failure"],
        )

        d = scenario.to_dict()
        assert d["scenario_id"] == "test_001"
        assert d["category"] == "common_flow"
        assert len(d["fault_configs"]) == 1


class TestGamePhase:
    """Tests for GamePhase enum values."""

    def test_all_phases_present(self) -> None:
        """All required phases are defined."""
        assert GamePhase.PREPARATION.value == "preparation"
        assert GamePhase.DETECTION.value == "detection"
        assert GamePhase.TRIAGE.value == "triage"
        assert GamePhase.CONTAINMENT.value == "containment"
        assert GamePhase.EVIDENCE_PRESERVATION.value == "evidence_preservation"
        assert GamePhase.RESTORE_REPAIR.value == "restore_repair"
        assert GamePhase.RECONCILIATION.value == "reconciliation"
        assert GamePhase.RE_CERTIFICATION.value == "re_certification"
        assert GamePhase.CLOSURE.value == "closure"


class TestFullPhaseSequence:
    """Tests for full alert-to-closure sequence."""

    def test_scenario_tracks_all_phases(self) -> None:
        """Scenario execution tracks through all incident phases."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_phase_test")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="phase_test",
            category=FaultCategory.COMMON_FLOW,
            description="Phase sequence test",
        )

        metrics, findings = orchestrator.execute_scenario(scenario, seed=42)

        # Check timeline has events for all phases
        phases_seen = {e.phase for e in orchestrator._timeline}
        assert GamePhase.PREPARATION in phases_seen
        assert GamePhase.DETECTION in phases_seen
        assert GamePhase.TRIAGE in phases_seen
        assert GamePhase.CONTAINMENT in phases_seen
        assert GamePhase.EVIDENCE_PRESERVATION in phases_seen
        assert GamePhase.RESTORE_REPAIR in phases_seen
        assert GamePhase.RECONCILIATION in phases_seen
        assert GamePhase.RE_CERTIFICATION in phases_seen
        assert GamePhase.CLOSURE in phases_seen

    def test_re_certification_triggers_on_integrity_violation(self) -> None:
        """Re-certification phase triggered when integrity violated."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_re_cert")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="integrity_violation",
            category=FaultCategory.MALFORMED_DATA,
            description="Integrity violation scenario",
            fault_configs=[{"fault_type": "integrity_violation", "phase": "during_operation"}],
        )

        metrics, findings = orchestrator.execute_scenario(scenario, seed=50)

        # Should have critical finding
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].certification_impact == "blocks_cert"
        assert metrics.data_integrity_verified is False

    def test_decision_correctness_calculated(self) -> None:
        """Decision correctness score is calculated for all scenarios."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_decision")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="decision_test",
            category=FaultCategory.COMMON_FLOW,
            description="Decision test",
        )

        metrics, _ = orchestrator.execute_scenario(scenario, seed=42)

        # Decision correctness should be set (default 0.99-1.0 for successful scenarios)
        assert 0.9 <= metrics.decision_correctness_score <= 1.0

    def test_communication_timing_recorded(self) -> None:
        """Communication timing is recorded in metrics."""
        orchestrator = GameDayOrchestrator()
        orchestrator.validate_authorization("gd_auth_comm")
        orchestrator.assert_safety_observer(True)

        scenario = GameDayScenario(
            scenario_id="comm_test",
            category=FaultCategory.OPERATOR_ERROR,
            description="Communication test",
        )

        metrics, _ = orchestrator.execute_scenario(scenario, seed=50)

        assert metrics.communication_timing_minutes >= 0


class TestFaultCategories:
    """Tests for FaultCategory enum values."""

    def test_all_categories_present(self) -> None:
        """All required fault categories are defined."""
        assert FaultCategory.COMMON_FLOW.value == "common_flow"
        assert FaultCategory.RARE_CRITICAL.value == "rare_critical"
        assert FaultCategory.HOSTILE_INPUT.value == "hostile_input"
        assert FaultCategory.PARTIAL_FAILURE.value == "partial_failure"
        assert FaultCategory.CONCURRENCY.value == "concurrency"
        assert FaultCategory.REPLAY.value == "replay"
        assert FaultCategory.TIMEOUT_RETRY.value == "timeout_retry"
        assert FaultCategory.NETWORK_PARTITION.value == "network_partition"
        assert FaultCategory.MALFORMED_DATA.value == "malformed_data"
        assert FaultCategory.LARGE_PAYLOAD.value == "large_payload"
        assert FaultCategory.VERSION_SKEW.value == "version_skew"
        assert FaultCategory.DEPENDENCY_OUTAGE.value == "dependency_outage"
        assert FaultCategory.OPERATOR_ERROR.value == "operator_error"
        assert FaultCategory.SECURITY_COMPROMISE.value == "security_compromise"