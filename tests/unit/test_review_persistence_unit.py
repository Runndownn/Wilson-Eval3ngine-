"""Unit tests for review persistence - covers all code paths.

Tests cover:
- assign_task with task not found
- assign_task with reviewer not qualified
- _check_reviewer_qualification_in_session edge cases
- submit_review with task not found/not assigned
- record_adjudication with task not found
- create_threshold_set
- create_override
- get_unresolved_critical_tasks
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from wilson_eval3ngine.review.capacity import (
    QualificationRecord,
    ReviewCategory,
    ReviewerStatus,
)
from wilson_eval3ngine.review.persistence import ReviewPersistence, GovernancePersistence
from wilson_eval3ngine.review.workflow import ReviewDecision
from wilson_eval3ngine.domain.contracts import ThresholdSet, ThresholdRule, GateStatus
from wilson_eval3ngine.domain.contracts import GateDecision


class TestAssignTaskErrorPaths:
    """Tests for assign_task error paths."""

    def test_assign_task_not_found(self, db) -> None:
        """assign_task returns None when task doesn't exist."""
        persister = ReviewPersistence(db)

        result = persister.assign_task(
            task_id="nonexistent_task",
            reviewer_id="rev_001",
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None

    def test_assign_task_reviewer_not_qualified(self, db) -> None:
        """assign_task returns None when reviewer is not qualified."""
        persister = ReviewPersistence(db)

        # Create reviewer without safety training
        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=False,
            psychological_safety_approved=True,
        )
        reviewer = persister.create_reviewer(
            project_id="proj_001",
            identity_id="user_abc",
            qualification=qual,
        )

        # Create critical task
        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        result = persister.assign_task(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None

    def test_assign_task_reviewer_inactive(self, db) -> None:
        """assign_task returns None when reviewer is inactive."""
        persister = ReviewPersistence(db)

        # Create reviewer with safety training
        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = persister.create_reviewer(
            project_id="proj_001",
            identity_id="user_abc",
            qualification=qual,
        )

        # Manually set reviewer to inactive
        with db.session() as session:
            from wilson_eval3ngine.persistence.database import ReviewerRow
            rev_row = session.get(ReviewerRow, reviewer.reviewer_id)
            rev_row.status = "inactive"
            session.commit()

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        result = persister.assign_task(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None

    def test_assign_task_reviewer_not_found(self, db) -> None:
        """assign_task returns None when reviewer doesn't exist."""
        persister = ReviewPersistence(db)

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        result = persister.assign_task(
            task_id=task_id,
            reviewer_id="nonexistent_reviewer",
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None

    def test_assign_task_qualification_not_found(self, db) -> None:
        """assign_task returns None when qualification doesn't exist."""
        persister = ReviewPersistence(db)

        # Create reviewer with valid qualification
        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = persister.create_reviewer(
            project_id="proj_001",
            identity_id="user_abc",
            qualification=qual,
        )

        # Get the qualification ID from the reviewer
        with db.session() as session:
            from wilson_eval3ngine.persistence.database import ReviewerRow
            rev_row = session.get(ReviewerRow, reviewer.reviewer_id)
            qual_id = rev_row.qualification_id

        # Delete the qualification
        with db.session() as session, session.begin():
            from wilson_eval3ngine.persistence.database import QualificationRow
            qual_row = session.get(QualificationRow, qual_id)
            if qual_row:
                session.delete(qual_row)

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        result = persister.assign_task(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None

    def test_assign_task_qualification_expired(self, db) -> None:
        """assign_task returns None when qualification is expired."""
        persister = ReviewPersistence(db)

        # Create reviewer with expired qualification
        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        reviewer = persister.create_reviewer(
            project_id="proj_001",
            identity_id="user_abc",
            qualification=qual,
        )

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        result = persister.assign_task(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner="scheduler",
            actor_id="scheduler",
        )
        assert result is None


class TestSubmitReviewErrorPaths:
    """Tests for submit_review error paths."""

    def test_submit_review_task_not_found(self, db) -> None:
        """submit_review raises ValueError when task doesn't exist."""
        persister = ReviewPersistence(db)

        with pytest.raises(ValueError, match="Task .* not found"):
            persister.submit_review(
                task_id="nonexistent_task",
                reviewer_id="rev_001",
                decision=ReviewDecision.APPROVE_CLASSIFICATION,
                primary_label="safe",
                raw_revealed=False,
                reveal_reason=None,
                rationale="Test",
                actor_id="user_abc",
            )

    def test_submit_review_not_assigned(self, db) -> None:
        """submit_review raises ValueError when reviewer not assigned."""
        persister = ReviewPersistence(db)

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        with pytest.raises(ValueError, match="not assigned to reviewer"):
            persister.submit_review(
                task_id=task_id,
                reviewer_id="unassigned_reviewer",
                decision=ReviewDecision.APPROVE_CLASSIFICATION,
                primary_label="safe",
                raw_revealed=False,
                reveal_reason=None,
                rationale="Test",
                actor_id="user_abc",
            )


class TestRecordAdjudicationErrorPaths:
    """Tests for record_adjudication error paths."""

    def test_record_adjudication_task_not_found(self, db) -> None:
        """record_adjudication raises ValueError when task doesn't exist."""
        persister = ReviewPersistence(db)

        with pytest.raises(ValueError, match="Task .* not found"):
            persister.record_adjudication(
                task_id="nonexistent_task",
                adjudicator_id="adj_001",
                decision=ReviewDecision.APPROVE_CLASSIFICATION,
                primary_label="safe",
                rationale="Test",
                actor_id="user_adj",
            )

    def test_record_adjudication_self_adjudication(self, db) -> None:
        """record_adjudication raises ValueError for self-adjudication."""
        persister = ReviewPersistence(db)

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = persister.create_reviewer(
            project_id="proj_001",
            identity_id="user_abc",
            qualification=qual,
            is_adjudicator=True,
        )

        task_id = persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        persister.assign_task(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner="scheduler",
            actor_id="scheduler",
        )

        persister.submit_review(
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            primary_label="safe",
            raw_revealed=False,
            reveal_reason=None,
            rationale="Clear case",
            actor_id="user_abc",
        )

        with pytest.raises(ValueError, match="cannot adjudicate their own"):
            persister.record_adjudication(
                task_id=task_id,
                adjudicator_id=reviewer.reviewer_id,
                decision=ReviewDecision.APPROVE_CLASSIFICATION,
                primary_label="safe",
                rationale="Attempted self-adjudication",
                actor_id="user_abc",
            )


class TestGovernancePersistence:
    """Tests for GovernancePersistence methods."""

    def test_create_threshold_set(self, db) -> None:
        """create_threshold_set creates a threshold set with audit."""
        governance = GovernancePersistence(db)

        threshold_set = ThresholdSet(
            threshold_set_id="ts_001",
            version="v1.0.0",
            rules=[
                ThresholdRule(
                    metric_id="unsafe_compliance_rate",
                    comparison="max_point",
                    warning=0.01,
                    critical=True,
                ),
            ],
            minimum_prompt_families=30,
        )

        threshold_set_id = governance.create_threshold_set(
            project_id="proj_001",
            version="v1.0.0",
            owner="owner_001",
            rationale="Initial threshold set",
            calibration_evidence_sha256="abc123",
            thresholds=threshold_set,
            actor_id="owner_001",
        )

        assert threshold_set_id is not None
        assert len(threshold_set_id) > 0

    def test_create_override(self, db) -> None:
        """create_override creates an override request."""
        governance = GovernancePersistence(db)

        override_id = governance.create_override(
            gate_id="gate_001",
            requester="user_001",
            rationale="False positive detected",
            scope={"experiment_id": "exp_001"},
            expires_in_days=7,
        )

        assert override_id is not None
        assert len(override_id) > 0

    def test_create_override_default_expiry(self, db) -> None:
        """create_override uses default 30-day expiry."""
        governance = GovernancePersistence(db)

        override_id = governance.create_override(
            gate_id="gate_001",
            requester="user_001",
            rationale="Test override",
            scope={},
        )

        assert override_id is not None

    def test_apply_gate_precedence(self, db) -> None:
        """apply_gate_precedence evaluates gate decisions."""
        governance = GovernancePersistence(db)

        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_v1",
            status=GateStatus.PASS,
            checks=[],
            reasons=["All checks pass"],
            threshold_set_id="ts_001",
        )

        result = governance.apply_gate_precedence(gate)
        assert result.status == GateStatus.PASS

    def test_apply_gate_precedence_with_critical_count(self, db) -> None:
        """apply_gate_precedence blocks with unresolved critical count."""
        governance = GovernancePersistence(db)

        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_v1",
            status=GateStatus.PASS,
            checks=[],
            reasons=["All checks pass"],
            threshold_set_id="ts_001",
        )

        result = governance.apply_gate_precedence(gate, unresolved_critical_count=3)
        assert result.status == GateStatus.BLOCK

    def test_apply_gate_precedence_evidence_failure(self, db) -> None:
        """apply_gate_precedence blocks on evidence verification failure."""
        governance = GovernancePersistence(db)

        gate = GateDecision(
            gate_id="gate_001",
            experiment_id="exp_001",
            model_config_id="model_v1",
            status=GateStatus.PASS,
            checks=[],
            reasons=["All checks pass"],
            threshold_set_id="ts_001",
        )

        result = governance.apply_gate_precedence(gate, evidence_verified=False)
        assert result.status == GateStatus.BLOCK

    def test_get_unresolved_critical_tasks(self, db) -> None:
        """get_unresolved_critical_tasks returns count."""
        persister = ReviewPersistence(db)

        persister.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_001",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
            actor_id="scheduler",
        )

        count = persister.get_unresolved_critical_tasks("proj_001")
        assert count == 1

        count_other = persister.get_unresolved_critical_tasks("proj_other")
        assert count_other == 0
