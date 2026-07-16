"""Unit tests for threshold versioning and override workflow (TODO 36).

Tests cover:
- VersionedThresholdSet validation
- OverrideRequest creation and approval
- OverrideEngine dual approval workflow
- DossierBuilder and verification
- Gate precedence rules
"""

import pytest
from datetime import datetime, timedelta, timezone

from wilson_eval3ngine.domain.contracts import GateDecision, GateStatus, ThresholdRule, ThresholdSet
from wilson_eval3ngine.review.governance import (
    DossierBuilder,
    GatePrecedence,
    OverrideEngine,
    OverrideRequest,
    OverrideStatus,
    VersionedThresholdSet,
)
from wilson_eval3ngine.util import utc_now


class TestVersionedThresholdSet:
    """Tests for VersionedThresholdSet."""

    def test_active_threshold_set(self):
        """Active threshold set is valid."""
        thresholds = ThresholdSet(
            threshold_set_id="release_v1",
            version="1.0.0",
            rules=[ThresholdRule(metric_id="test_metric", comparison="max_point")],
        )
        
        vts = VersionedThresholdSet(
            threshold_set_id="release_v1",
            version="1.0.0",
            owner="measurement_team",
            rationale="Initial release thresholds",
            calibration_evidence_sha256="abc123",
            thresholds=thresholds,
            approved_by=["approver_a", "approver_b"],
        )
        
        assert vts.is_active() is True

    def test_threshold_without_dual_approval(self):
        """Threshold set requires dual approval."""
        thresholds = ThresholdSet(
            threshold_set_id="release_v2",
            version="1.0.0",
            rules=[ThresholdRule(metric_id="test_metric", comparison="max_point")],
        )
        
        vts = VersionedThresholdSet(
            threshold_set_id="release_v2",
            version="1.0.0",
            owner="measurement_team",
            rationale="Test thresholds",
            calibration_evidence_sha256="abc123",
            thresholds=thresholds,
            approved_by=["approver_a"],  # Missing second approver
        )
        
        assert vts.is_active() is False

    def test_threshold_future_effective_date(self):
        """Future effective date makes threshold inactive."""
        thresholds = ThresholdSet(
            threshold_set_id="release_v3",
            version="1.0.0",
            rules=[ThresholdRule(metric_id="test_metric", comparison="max_point")],
        )
        
        vts = VersionedThresholdSet(
            threshold_set_id="release_v3",
            version="1.0.0",
            owner="measurement_team",
            rationale="Future thresholds",
            calibration_evidence_sha256="abc123",
            thresholds=thresholds,
            approved_by=["approver_a", "approver_b"],
            effective_from=datetime.now(timezone.utc) + timedelta(days=1),
        )
        
        assert vts.is_active() is False


class TestOverrideRequest:
    """Tests for OverrideRequest."""

    def test_pending_override(self):
        """Pending override is not approved."""
        req = OverrideRequest(
            override_id="ovr_001",
            gate_id="gate_abc",
            requester="user_abc",
            rationale="Exception for known false positive",
        )
        
        assert req.is_approved() is False

    def test_dual_approval_required(self):
        """Dual approval is tracked correctly."""
        req = OverrideRequest(
            override_id="ovr_002",
            gate_id="gate_abc",
            requester="user_abc",
            rationale="Test override",
            approver_a="approver_a",
        )
        
        assert req.is_approved() is False
        
        # Add second approver
        updated = OverrideRequest(
            override_id=req.override_id,
            gate_id=req.gate_id,
            requester=req.requester,
            rationale=req.rationale,
            approver_a=req.approver_a,
            approver_b="approver_b",
            approved_at=None,
            created_at=req.created_at,
            expires_at=req.expires_at,
        )
        
        assert updated.is_approved() is True

    def test_expired_override(self):
        """Expired override is detected."""
        req = OverrideRequest(
            override_id="ovr_003",
            gate_id="gate_abc",
            requester="user_abc",
            rationale="Test override",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        
        assert req.is_expired() is True


class TestOverrideEngine:
    """Tests for OverrideEngine."""

    def test_create_override(self):
        """Override request is created correctly."""
        engine = OverrideEngine()
        
        req = engine.create_override(
            gate_id="gate_001",
            requester="user_abc",
            rationale="False positive due to ambiguous prompt formatting",
            scope={"gate_check": "WE3-SAFE-UCR"},
        )
        
        assert req.override_id is not None
        assert req.gate_id == "gate_001"
        assert req.is_approved() is False

    def test_approve_override(self):
        """Override can be approved by two approvers."""
        engine = OverrideEngine()
        
        req = engine.create_override(
            gate_id="gate_001",
            requester="user_abc",
            rationale="Test override",
            scope={"gate_check": "test_metric"},
        )
        
        # First approval
        approved1 = engine.approve_override(req.override_id, "approver_a")
        assert approved1.approver_a == "approver_a"
        assert approved1.is_approved() is False
        
        # Second approval
        approved2 = engine.approve_override(req.override_id, "approver_b")
        assert approved2.approver_b == "approver_b"
        assert approved2.is_approved() is True

    def test_apply_override_to_gate(self):
        """Approved override modifies gate decision."""
        engine = OverrideEngine()
        
        req = engine.create_override(
            gate_id="gate_001",
            requester="user_abc",
            rationale="False positive override",
            scope={"gate_check": "WE3-SAFE-UCR"},
        )
        
        # Dual approval
        engine.approve_override(req.override_id, "approver_a")
        approved_req = engine.approve_override(req.override_id, "approver_b")
        
        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_abc",
            status=GateStatus.BLOCK,
            checks=[],
            reasons=["Unsafe compliance rate too high"],
            threshold_set_id="release_v1",
        )
        
        overridden = engine.apply_override(gate, approved_req)
        
        assert overridden.status == GateStatus.WARNING  # Override yields warning
        assert "OVERRIDE APPLIED" in overridden.reasons[0]

    def test_cannot_apply_unapproved_override(self):
        """Unapproved override cannot be applied."""
        engine = OverrideEngine()
        
        req = engine.create_override(
            gate_id="gate_001",
            requester="user_abc",
            rationale="Test override",
            scope={},
        )
        
        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_abc",
            status=GateStatus.BLOCK,
            checks=[],
            reasons=[],
            threshold_set_id="release_v1",
        )
        
        with pytest.raises(ValueError, match="unapproved"):
            engine.apply_override(gate, req)


class TestDossierBuilder:
    """Tests for DossierBuilder."""

    def test_build_dossier(self):
        """Dossier is built with all required elements."""
        builder = DossierBuilder()
        
        dossier = builder.build_dossier(
            experiment_id="exp_001",
            project_id="proj_001",
            manifest_hash="manifest_sha",
            dataset_hash="dataset_sha",
            snapshots=[],
            gates=[],
            overrides=[],
            limitations=["Foundation release - no certification claim"],
        )
        
        assert dossier["experiment_id"] == "exp_001"
        assert dossier["project_id"] == "proj_001"
        assert dossier["manifest_hash"] == "manifest_sha"
        assert "metric_snapshots" in dossier
        assert "limitations" in dossier

    def test_dossier_with_overrides(self):
        """Dossier includes approved overrides."""
        builder = DossierBuilder()
        
        override = OverrideRequest(
            override_id="ovr_001",
            gate_id="gate_001",
            requester="user_abc",
            rationale="Test override",
            approver_a="approver_a",
            approver_b="approver_b",
            approved_at=utc_now(),
        )
        
        dossier = builder.build_dossier(
            experiment_id="exp_001",
            project_id="proj_001",
            manifest_hash="manifest_sha",
            dataset_hash="dataset_sha",
            snapshots=[],
            gates=[],
            overrides=[override],
            limitations=[],
        )
        
        assert len(dossier["overrides"]) == 1
        assert dossier["overrides"][0]["override_id"] == "ovr_001"

    def test_verify_dossier_integrity(self):
        """Dossier integrity verification works."""
        builder = DossierBuilder()
        
        # Valid dossier
        valid_dossier = {
            "experiment_id": "exp_001",
            "manifest_hash": "sha",
            "dataset_hash": "sha",
            "metric_snapshots": [],
            "gate_decisions": [],
        }
        
        assert builder.verify_dossier_integrity(valid_dossier) is True
        
        # Missing field
        invalid_dossier = {
            "experiment_id": "exp_001",
            # Missing required fields
        }
        
        assert builder.verify_dossier_integrity(invalid_dossier) is False


class TestGatePrecedence:
    """Tests for GatePrecedence rules."""

    def test_precedence_levels_exist(self):
        """Precedence levels are defined for all gate types."""
        assert hasattr(GatePrecedence, "PRECEDENCE")
        assert "integrity_check" in GatePrecedence.PRECEDENCE
        assert "critical_raw_safety" in GatePrecedence.PRECEDENCE
        assert "support_threshold" in GatePrecedence.PRECEDENCE
        assert "composite_score" in GatePrecedence.PRECEDENCE
        
        # Critical safety should outrank composite
        assert GatePrecedence.PRECEDENCE["critical_raw_safety"] > GatePrecedence.PRECEDENCE["composite_score"]

    def test_evaluate_preserves_decision(self):
        """Evaluate method returns gate decision."""
        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_abc",
            status=GateStatus.BLOCK,
            checks=[],
            reasons=["Test block"],
            threshold_set_id="release_v1",
        )
        
        result = GatePrecedence.evaluate(gate)
        
        assert result.gate_id == gate.gate_id
        assert result.status == gate.status