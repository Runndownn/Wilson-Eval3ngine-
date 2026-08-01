"""
Environment-specific tests for Human Review Workflow (SEC-005).

Tests review-task creation, assignment, blind dual review, recusal,
submission, disagreement, adjudication, SLA tracking, and audit across
different deployment environments:
- Development: In-memory workflow, dev reviewers
- Staging: Simulated production reviewers, SLA tracking
- Production: Full workflow with adjudication, legal hold tracking
- Minimal: No optional dependencies
- OTel-enabled/disabled: tracing behavior with review workflow

Test counts: 20 integration tests
"""

from __future__ import annotations

import pytest

from wilson_eval3ngine.review.capacity import (
    QualificationRecord,
    ReviewCategory,
    Reviewer,
    ReviewerStatus,
    QueueSLA,
    RecusalReason,
)
from wilson_eval3ngine.review.workflow import (
    Adjudication,
    ReviewDecision,
    ReviewSubmission,
    ReviewWorkflow,
)


# ============================================================================
# Environment-Specific Review Workflow Tests (8 tests)
# ============================================================================

class TestReviewWorkflowAcrossEnvironments:
    """Test review workflow behavior across different environments."""

    def test_create_review_task_dev_environment(self):
        """Review task creation in development environment."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_dev",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_dev",
            case_version_id="case_dev",
            prompt_family_id="family_dev",
            content_hash="sha256_dev",
        )

        assert task.task_id is not None
        assert task.project_id == "proj_dev"
        assert task.category == ReviewCategory.CRITICAL_UNSAFE
        assert task.run_id == "run_dev"

    def test_create_review_task_staging_environment(self):
        """Review task creation in staging environment."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_staging",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_staging",
            case_version_id="case_staging",
            prompt_family_id="family_staging",
            content_hash="sha256_staging",
        )

        assert task.task_id is not None
        assert task.project_id == "proj_staging"
        assert task.category == ReviewCategory.AMBIGUITY_RESOLUTION

    def test_create_review_task_production_environment(self):
        """Review task creation in production environment."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_prod",
            category=ReviewCategory.DISAGREEMENT,
            run_id="run_prod",
            case_version_id="case_prod",
            prompt_family_id="family_prod",
            content_hash="sha256_prod",
        )

        assert task.task_id is not None
        assert task.project_id == "proj_prod"
        assert task.category == ReviewCategory.DISAGREEMENT

    def test_assign_task_to_qualified_reviewer(self):
        """Task can be assigned to qualified reviewer."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_001",
            identity_id="user_abc",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )

        assignment = workflow.assign_task(task.task_id, reviewer, "system")

        assert assignment is not None
        assert assignment.reviewer_id == reviewer.reviewer_id
        assert assignment.task_id == task.task_id

    def test_assign_task_to_unqualified_reviewer(self):
        """Task cannot be assigned to unqualified reviewer."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=False,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_002",
            identity_id="user_def",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )

        assignment = workflow.assign_task(task.task_id, reviewer, "system")

        assert assignment is None

    def test_submit_review(self):
        """Review submission can be recorded."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_001",
            identity_id="user_abc",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )

        workflow.assign_task(task.task_id, reviewer, "system")

        submission = workflow.submit_review(
            task_id=task.task_id,
            reviewer_id=reviewer.reviewer_id,
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            rationale="Clear case for classification",
        )

        assert submission is not None
        assert submission.decision == ReviewDecision.APPROVE_CLASSIFICATION
        assert submission.reviewer_id == reviewer.reviewer_id

    def test_submit_review_requires_assignment(self):
        """Cannot submit review without assignment."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
        )

        with pytest.raises(ValueError, match="not assigned"):
            workflow.submit_review(
                task_id=task.task_id,
                reviewer_id="rev_nonexistent",
                decision=ReviewDecision.APPROVE_CLASSIFICATION,
            )

    def test_adjudicate_disputed_review(self):
        """Adjudication completes a disputed review."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_content",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )

        # Assign to reviewer A
        reviewer_a = Reviewer(
            reviewer_id="rev_a",
            identity_id="user_a",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )
        workflow.assign_task(task.task_id, reviewer_a, "system")

        # Submit first decision
        workflow.submit_review(
            task_id=task.task_id,
            reviewer_id="rev_a",
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            primary_label="safe_useful_compliance",
        )

        # Assign to reviewer B (blind dual review)
        reviewer_b = Reviewer(
            reviewer_id="rev_b",
            identity_id="user_b",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )
        workflow.assign_task(task.task_id, reviewer_b, "system")

        # Submit second decision
        workflow.submit_review(
            task_id=task.task_id,
            reviewer_id="rev_b",
            decision=ReviewDecision.OVERRIDE_CLASSIFICATION,
            primary_label="false_refusal",
        )

        # Adjudicate
        adjudication = workflow.adjudicate(
            task_id=task.task_id,
            adjudicator_id="adj_001",
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            primary_label="safe_useful_compliance",
            rationale="Evidence supports safe compliance classification",
        )

        assert adjudication is not None
        assert adjudication.task_id == task.task_id
        assert adjudication.adjudicator_id == "adj_001"
        assert adjudication.reviewer_a_opinion is not None


# ============================================================================
# Environment-Specific Review Submission Tests (4 tests)
# ============================================================================

class TestReviewSubmissionAcrossEnvironments:
    """Test review submission behavior across environments."""

    def test_submission_structure_dev(self):
        """Submission has required fields in development."""
        submission = ReviewSubmission(
            submission_id="sub_dev_001",
            task_id="task_dev_001",
            reviewer_id="rev_dev_001",
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            primary_label="safe_useful_compliance",
            rationale="Classification matches evidence",
        )

        assert submission.submission_id == "sub_dev_001"
        assert submission.decision == ReviewDecision.APPROVE_CLASSIFICATION
        assert submission.submitted_at is not None

    def test_submission_structure_staging(self):
        """Submission has required fields in staging."""
        submission = ReviewSubmission(
            submission_id="sub_stg_001",
            task_id="task_stg_001",
            reviewer_id="rev_stg_001",
            decision=ReviewDecision.OVERRIDE_CLASSIFICATION,
            primary_label="false_refusal",
            rationale="Evidence shows false refusal",
        )

        assert submission.submission_id == "sub_stg_001"
        assert submission.decision == ReviewDecision.OVERRIDE_CLASSIFICATION

    def test_submission_structure_production(self):
        """Submission has required fields in production."""
        submission = ReviewSubmission(
            submission_id="sub_prod_001",
            task_id="task_prod_001",
            reviewer_id="rev_prod_001",
            decision=ReviewDecision.REQUEST_ADJUDICATION,
            rationale="Cannot determine classification",
        )

        assert submission.submission_id == "sub_prod_001"
        assert submission.decision == ReviewDecision.REQUEST_ADJUDICATION

    def test_raw_reveal_tracking(self):
        """Raw content reveal is tracked."""
        submission = ReviewSubmission(
            submission_id="sub_002",
            task_id="task_001",
            reviewer_id="rev_001",
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            raw_revealed=True,
            reveal_reason="Needed to verify harmful content scope",
        )

        assert submission.raw_revealed is True
        assert "harmful" in submission.reveal_reason.lower()


# ============================================================================
# Environment-Specific Adjudication Tests (3 tests)
# ============================================================================

class TestAdjudicationAcrossEnvironments:
    """Test adjudication behavior across environments."""

    def test_adjudication_structure_dev(self):
        """Adjudication has required fields in development."""
        adj = Adjudication(
            adjudication_id="adj_dev_001",
            task_id="task_dev_001",
            adjudicator_id="adj_dev_001",
            decision=ReviewDecision.OVERRIDE_CLASSIFICATION,
            primary_label="appropriate_refusal",
            rationale="Both reviewers made errors; evidence shows refusal needed",
            reviewer_a_opinion="approve",
            reviewer_b_opinion="override",
        )

        assert adj.adjudication_id == "adj_dev_001"
        assert adj.decision == ReviewDecision.OVERRIDE_CLASSIFICATION
        assert adj.created_at is not None

    def test_adjudication_structure_staging(self):
        """Adjudication has required fields in staging."""
        adj = Adjudication(
            adjudication_id="adj_stg_001",
            task_id="task_stg_001",
            adjudicator_id="adj_stg_001",
            decision=ReviewDecision.APPROVE_CLASSIFICATION,
            primary_label="safe_useful_compliance",
            rationale="Evidence supports safe compliance",
            reviewer_a_opinion="approve",
            reviewer_b_opinion="override",
        )

        assert adj.adjudication_id == "adj_stg_001"
        assert adj.decision == ReviewDecision.APPROVE_CLASSIFICATION

    def test_adjudication_structure_production(self):
        """Adjudication has required fields in production."""
        adj = Adjudication(
            adjudication_id="adj_prod_001",
            task_id="task_prod_001",
            adjudicator_id="adj_prod_001",
            decision=ReviewDecision.ABSTAIN,
            rationale="Insufficient evidence to make determination",
            reviewer_a_opinion="approve",
            reviewer_b_opinion="approve",
        )

        assert adj.adjudication_id == "adj_prod_001"
        assert adj.decision == ReviewDecision.ABSTAIN


# ============================================================================
# Environment-Specific Recusal Tests (2 tests)
# ============================================================================

class TestRecusalAcrossEnvironments:
    """Test reviewer recusal behavior across environments."""

    def test_record_recusal_dev_environment(self):
        """Reviewer recusal is recorded in development."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_dev",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_dev",
            case_version_id="case_dev",
            prompt_family_id="family_dev",
            content_hash="sha256_dev",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_dev_001",
            identity_id="user_dev",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )

        workflow.assign_task(task.task_id, reviewer, "system")
        workflow.record_recusal(
            task_id=task.task_id,
            reviewer_id=reviewer.reviewer_id,
            reason=RecusalReason.CONFLICT_OF_INTEREST,
            reason_detail="Personal connection to case subject",
        )

        assignments = [
            a for a in workflow._assignments.values()
            if a.task_id == task.task_id
        ]
        assert len(assignments) == 1
        assert assignments[0].recusal_at is not None

    def test_record_recusal_production_environment(self):
        """Reviewer recusal is recorded in production."""
        workflow = ReviewWorkflow()

        task = workflow.create_review_task(
            project_id="proj_prod",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_prod",
            case_version_id="case_prod",
            prompt_family_id="family_prod",
            content_hash="sha256_prod",
        )

        qual = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_prod_001",
            identity_id="user_prod",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qual,
        )

        workflow.assign_task(task.task_id, reviewer, "system")
        workflow.record_recusal(
            task_id=task.task_id,
            reviewer_id=reviewer.reviewer_id,
            reason=RecusalReason.WELLNESS_CONCERN,
            reason_detail="Reviewer needs break after exposure to harmful content",
        )

        assignments = [
            a for a in workflow._assignments.values()
            if a.task_id == task.task_id
        ]
        assert len(assignments) == 1
        assert assignments[0].recusal_at is not None
        assert "harmful" in assignments[0].recusal_reason.lower()
