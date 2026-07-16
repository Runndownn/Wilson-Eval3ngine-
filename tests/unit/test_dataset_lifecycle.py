"""
Tests for Dataset Lifecycle State Machine and Promotion Controls.

Validates T2.1.4 requirements for supply-chain controls.
"""


from wilson_eval3ngine.benchmark.lifecycle import (
    DatasetLifecycle,
    DatasetLifecycleState,
    HiddenSetAllocation,
)


class TestDatasetLifecycle:
    """Tests for lifecycle state transitions."""

    def test_initial_state_is_draft(self):
        """New datasets start in DRAFT state."""
        lifecycle = DatasetLifecycle()
        state = lifecycle.get_state("ds_test_1_0_0")
        assert state == DatasetLifecycleState.DRAFT

    def test_draft_to_reviewed_transition(self):
        """DRAFT to REVIEWED transition allowed."""
        lifecycle = DatasetLifecycle()
        assert lifecycle.can_transition(
            "ds_test_1_0_0",
            DatasetLifecycleState.REVIEWED,
            ["author-1"]
        ) is True

    def test_approved_requires_dual_approval(self):
        """APPROVED state requires dual independent approvals."""
        lifecycle = DatasetLifecycle()

        # Single approval not enough
        assert lifecycle.can_transition(
            "ds_test_1_0_0",
            DatasetLifecycleState.APPROVED,
            ["reviewer-1"]
        ) is False

        # Dual approval required
        assert lifecycle.can_transition(
            "ds_test_1_0_0",
            DatasetLifecycleState.APPROVED,
            ["reviewer-1", "reviewer-2"]
        ) is True

    def test_approved_to_deprecated_allowed(self):
        """APPROVED to DEPRECATED transition allowed."""
        lifecycle = DatasetLifecycle()
        lifecycle._current_state["ds_test_1_0_0"] = DatasetLifecycleState.APPROVED

        assert lifecycle.can_transition(
            "ds_test_1_0_0",
            DatasetLifecycleState.DEPRECATED,
            ["reviewer-1", "reviewer-2"]
        ) is True

    def test_no_reverse_transitions(self):
        """Cannot reverse from APPROVED to earlier states."""
        lifecycle = DatasetLifecycle()
        lifecycle._current_state["ds_test_1_0_0"] = DatasetLifecycleState.APPROVED

        assert lifecycle.can_transition(
            "ds_test_1_0_0",
            DatasetLifecycleState.DRAFT,
            ["reviewer-1", "reviewer-2"]
        ) is False


class TestHiddenSetAllocation:
    """Tests for hidden set separation configuration."""

    def test_hidden_set_allocation_structure(self):
        """Hidden set allocation has required fields."""
        allocation = HiddenSetAllocation(
            tranche_id="tranche-a",
            hidden_percent=20.0,
            purpose="calibration_validation",
        )

        assert allocation.tranche_id == "tranche-a"
        assert allocation.hidden_percent == 20.0
        assert allocation.purpose == "calibration_validation"

    def test_object_store_policy_includes_encryption(self):
        """Object store policy requires encryption."""
        allocation = HiddenSetAllocation(
            tranche_id="tranche-a",
            hidden_percent=20.0,
            purpose="calibration_validation",
        )

        assert allocation.object_store_policy["encryption_required"] is True
        assert allocation.object_store_policy["export_restricted"] is True
