"""Unit tests for Retention Models (TODO 10)."""

from datetime import UTC, datetime, timedelta

import pytest

from wilson_eval3ngine.retention.retention_models import (
    HoldType,
    ProposedAction,
    ReferenceMap,
    RetentionHold,
    RetentionLifeCycleState,
    RetentionPolicyService,
    RetentionRule,
    RetentionStateMatrix,
    SafetyStatus,
    get_retention_policy_service,
)


@pytest.fixture
def sample_rule() -> RetentionRule:
    """Create a sample retention rule for testing."""
    return RetentionRule(
        policy_version="v1.0.0",
        raw_content_policy="retain-governed",
        derivative_policy="retain-reviewed-only",
    )


@pytest.fixture
def sample_hold() -> RetentionHold:
    """Create a sample hold for testing."""
    return RetentionHold(
        hold_type=HoldType.LEGAL,
        reason="Evidence preservation required",
        applied_at=datetime.now(tz=UTC),
        correlation_id="corr:test-123",
    )


@pytest.fixture
def sample_expired_hold() -> RetentionHold:
    """Create an expired hold for testing."""
    return RetentionHold(
        hold_type=HoldType.POLICY,
        reason="Temporary migration hold",
        applied_at=datetime.now(tz=UTC) - timedelta(days=30),
        expires_at=datetime.now(tz=UTC) - timedelta(days=1),
        correlation_id="corr:test-expired",
    )


class TestRetentionLifeCycleState:
    """Test suite for retention lifecycle states."""

    def test_all_ten_states_exist(self):
        """Verify all 10 required lifecycle states exist."""
        states = [s.value for s in RetentionLifeCycleState]
        expected = [
            "active",
            "superseded",
            "withdrawn",
            "deleted_occurrence",
            "archived",
            "quarantined",
            "held",
            "audit_linked",
            "recoverable",
            "eligible_for_destruction",
        ]
        for expected_state in expected:
            assert expected_state in states, f"Missing state: {expected_state}"

    def test_state_values_are_strings(self):
        """Verify states are string enums."""
        for state in RetentionLifeCycleState:
            assert isinstance(state.value, str)


class TestHoldType:
    """Test suite for hold types."""

    def test_all_hold_types_exist(self):
        """Verify all hold types exist."""
        hold_types = [h.value for h in HoldType]
        expected = ["legal", "policy", "migration", "rollback"]
        for expected_type in expected:
            assert expected_type in hold_types, f"Missing hold type: {expected_type}"


class TestProposedAction:
    """Test suite for proposed actions."""

    def test_all_actions_exist(self):
        """Verify all proposed actions exist."""
        actions = [a.value for a in ProposedAction]
        expected = ["delete", "archive", "quarantine", "none"]
        for expected_action in expected:
            assert expected_action in actions, f"Missing action: {expected_action}"


class TestRetentionRule:
    """Test suite for retention rules."""

    def test_valid_rule_creation(self, sample_rule: RetentionRule):
        """Verify retention rule can be created."""
        assert sample_rule.policy_version == "v1.0.0"
        assert sample_rule.raw_content_policy == "retain-governed"
        assert sample_rule.derivative_policy == "retain-reviewed-only"

    def test_raw_content_policy_choices(self):
        """Verify raw content policy choices."""
        for policy in ["retain-restricted", "retain-governed", "discard-after-compile"]:
            rule = RetentionRule(
                policy_version="v1.0.0",
                raw_content_policy=policy,  # type: ignore
                derivative_policy="retain",
            )
            assert rule.raw_content_policy == policy

    def test_derivative_policy_choices(self):
        """Verify derivative policy choices."""
        for policy in ["retain", "retain-reviewed-only", "ephemeral"]:
            rule = RetentionRule(
                policy_version="v1.0.0",
                raw_content_policy="retain-restricted",
                derivative_policy=policy,  # type: ignore
            )
            assert rule.derivative_policy == policy


class TestRetentionHold:
    """Test suite for retention holds."""

    def test_valid_hold_creation(self, sample_hold: RetentionHold):
        """Verify hold can be created."""
        assert sample_hold.hold_type == HoldType.LEGAL
        assert sample_hold.reason == "Evidence preservation required"
        assert sample_hold.correlation_id == "corr:test-123"

    def test_hold_expiry(self, sample_expired_hold: RetentionHold):
        """Verify hold can have expiry datetime."""
        assert sample_expired_hold.expires_at is not None
        assert sample_expired_hold.expires_at < datetime.now(tz=UTC)


class TestReferenceMap:
    """Test suite for reference map."""

    def test_empty_reference_map(self):
        """Verify empty reference map."""
        ref_map = ReferenceMap()
        assert ref_map.total_reference_count() == 0

    def test_reference_map_with_entries(self):
        """Verify reference map counts entries."""
        ref_map = ReferenceMap(
            canonical=["rudi-k:abc123", "rudi-k:def456"],
            projected=["proj:123"],
            audit=["audit:456"],
        )
        assert ref_map.total_reference_count() == 4
        assert len(ref_map.canonical) == 2

    def test_all_ten_reference_types_exist(self):
        """Verify all 10 reference types are present."""
        ref_map = ReferenceMap()
        expected_attrs = [
            "canonical",
            "projected",
            "audit",
            "migration",
            "rollback",
            "cluster",
            "tombstone",
            "outbox_event",
            "cursor",
            "disposable_projection",
        ]
        for attr in expected_attrs:
            assert hasattr(ref_map, attr), f"Missing reference type: {attr}"


class TestSafetyStatus:
    """Test suite for safety status."""

    def test_unsafe_by_default(self):
        """Verify safety status is unsafe by default."""
        status = SafetyStatus()
        assert status.deletion_safe is False
        assert status.reference_count == 0
        assert status.hold_count == 0
        assert status.audit_preserved is True

    def test_safe_status(self):
        """Verify safe status can be created."""
        status = SafetyStatus(
            deletion_safe=True,
            reference_count=0,
            hold_count=0,
            audit_preserved=True,
        )
        assert status.deletion_safe is True


class TestRetentionStateMatrix:
    """Test suite for retention state matrix."""

    def test_valid_matrix_creation(self, sample_rule: RetentionRule):
        """Verify matrix can be created."""
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
        )
        assert matrix.object_id == "rudi-k:abc123def456abc123def456"
        assert matrix.scope == "kb"

    def test_object_id_validation(self, sample_rule: RetentionRule):
        """Verify object ID must match rudi-k pattern."""
        with pytest.raises(ValueError):
            RetentionStateMatrix(
                object_id="invalid-id",
                scope="kb",
                retention_rule=sample_rule,
            )

    def test_evaluate_deletion_safety_with_holds(self, sample_rule: RetentionRule, sample_hold: RetentionHold):
        """Verify holds block deletion."""
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
            holds=[sample_hold],
        )
        safety = matrix.evaluate_deletion_safety()
        assert safety.deletion_safe is False
        assert safety.hold_count == 1

    def test_evaluate_deletion_safety_expired_holds(self, sample_rule: RetentionRule, sample_expired_hold: RetentionHold):
        """Verify expired holds do not block deletion."""
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
            holds=[sample_expired_hold],
        )
        safety = matrix.evaluate_deletion_safety()
        assert safety.hold_count == 0

    def test_evaluate_deletion_safety_with_references(self, sample_rule: RetentionRule):
        """Verify references block deletion."""
        ref_map = ReferenceMap(canonical=["rudi-k:ref1"])
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
            references=ref_map,
        )
        safety = matrix.evaluate_deletion_safety()
        assert safety.deletion_safe is False
        assert safety.reference_count == 1

    def test_generate_dry_run_report(self, sample_rule: RetentionRule):
        """Verify dry run report generation."""
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
            proposed_action=ProposedAction.DELETE,
        )
        report = matrix.generate_dry_run_report()
        assert "object_id" in report
        assert "proposed_action" in report
        assert report["dry_run_only"] is True

    def test_legal_hold_blocks_deletion(self, sample_rule: RetentionRule):
        """Verify legal hold blocks deletion regardless of other factors."""
        sample_rule.legal_hold = True
        matrix = RetentionStateMatrix(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            retention_rule=sample_rule,
        )
        safety = matrix.evaluate_deletion_safety()
        assert safety.deletion_safe is False


class TestRetentionPolicyService:
    """Test suite for retention policy service."""

    def test_service_creation(self):
        """Verify service can be created."""
        service = RetentionPolicyService()
        assert service is not None

    def test_evaluate_object(self, sample_rule: RetentionRule):
        """Verify object evaluation."""
        service = RetentionPolicyService()
        matrix = service.evaluate_object(
            object_id="rudi-k:abc123def456abc123def456",
            scope="kb",
            lifecycle_state=RetentionLifeCycleState.ACTIVE,
            retention_rule=sample_rule,
        )
        assert isinstance(matrix, RetentionStateMatrix)
        assert matrix.safety_status is not None

    def test_validate_approval(self, sample_rule: RetentionRule):
        """Verify approval validation."""
        service = RetentionPolicyService()
        valid_approval = {
            "approved": True,
            "approved_by": "operator",
            "approval_hash": "abc123",
            "policy_version": "v1.0.0",
        }
        assert service.validate_approval(valid_approval, "v1.0.0") is True

        invalid_approval = {
            "approved": False,
            "approved_by": "operator",
            "approval_hash": "abc123",
        }
        assert service.validate_approval(invalid_approval, "v1.0.0") is False

    def test_get_retention_policy_service(self):
        """Verify singleton accessor."""
        service = get_retention_policy_service()
        assert isinstance(service, RetentionPolicyService)