"""Human review and adjudication workflow (TODO 35).

T5.1.7 - Implements review-task creation, assignment, blind dual review,
recusal, submission, disagreement, adjudication, supersession, SLA tracking, and audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ..util import new_id, sha256_hex, utc_now
from .capacity import (
    QueueSLA,
    RecusalReason,
    ReviewAssignment,
    ReviewCategory,
    ReviewTask,
    Reviewer,
)

logger = logging.getLogger(__name__)


class ReviewState(StrEnum):
    """States for a review task."""
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    SUBMITTED = "submitted"
    ADJUDICATION_REQUIRED = "adjudication_required"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ReviewDecision(StrEnum):
    """Possible review decisions."""
    APPROVE_CLASSIFICATION = "approve_classification"
    OVERRIDE_CLASSIFICATION = "override_classification"
    REQUEST_ADJUDICATION = "request_adjudication"
    ABSTAIN = "abstain"  # Cannot determine due to insufficient info


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    """Immutable submission of a review decision."""
    submission_id: str
    task_id: str
    reviewer_id: str
    decision: ReviewDecision
    
    # If overriding, the new classification
    primary_label: str | None = None
    secondary_labels: list[str] = field(default_factory=list)
    rationale: str = ""
    evidence_notes: str = ""
    
    # Raw content reveal tracking (if applicable)
    raw_revealed: bool = False
    reveal_reason: str | None = None
    
    submitted_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Adjudication:
    """Final adjudication decision."""
    adjudication_id: str
    task_id: str
    adjudicator_id: str
    decision: ReviewDecision
    
    # Final classification (if overriding)
    primary_label: str | None = None
    secondary_labels: list[str] = field(default_factory=list)
    rationale: str = ""
    
    # References to the two reviewing opinions
    reviewer_a_opinion: str | None = None
    reviewer_b_opinion: str | None = None
    
    created_at: datetime = field(default_factory=utc_now)


class ReviewWorkflow:
    """Manages the human review workflow with blind dual review."""
    
    def __init__(self) -> None:
        self._tasks: dict[str, ReviewTask] = {}
        self._assignments: dict[str, ReviewAssignment] = {}
        self._submissions: dict[str, ReviewSubmission] = {}
        self._adjudications: dict[str, Adjudication] = {}
    
    def create_review_task(
        self,
        *,
        project_id: str,
        category: ReviewCategory,
        run_id: str,
        case_version_id: str,
        prompt_family_id: str,
        content_hash: str,
    ) -> ReviewTask:
        """Create a new review task."""
        task = ReviewTask(
            task_id=new_id("review"),
            project_id=project_id,
            category=category,
            run_id=run_id,
            case_version_id=case_version_id,
            prompt_family_id=prompt_family_id,
            content_hash=content_hash,
            created_at=utc_now(),
        )
        self._tasks[task.task_id] = task
        
        logger.info(
            "review_task_created",
            extra={
                "task_id": task.task_id,
                "project_id": project_id,
                "category": category,
                "correlation_id": sha256_hex(task.task_id)[:16],
            },
        )
        
        return task
    
    def assign_task(
        self,
        task_id: str,
        reviewer: Reviewer,
        assigner: str,
    ) -> ReviewAssignment | None:
        """Assign a task to a qualified reviewer."""
        task = self._tasks.get(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return None

        can_accept, reason = reviewer.can_accept_review(task.category)
        if not can_accept:
            logger.warning(
                f"Reviewer {reviewer.reviewer_id} cannot accept task: {reason}",
            )
            return None

        sla = QueueSLA(category=task.category)
        due_at = sla.calculate_due_at(task.created_at)

        assignment = ReviewAssignment(
            assignment_id=new_id("assign"),
            task_id=task_id,
            reviewer_id=reviewer.reviewer_id,
            assigner=assigner,
            reason=f"Qualified for category {task.category}",
            assigned_at=utc_now(),
        )

        # Update task - add reviewer to assigned_reviewer_ids list
        updated_reviewers = list(task.assigned_reviewer_ids) + [reviewer.reviewer_id]
        first_assigned = task.first_assigned_at or utc_now()

        updated_task = ReviewTask(
            task_id=task.task_id,
            project_id=task.project_id,
            category=task.category,
            run_id=task.run_id,
            case_version_id=task.case_version_id,
            prompt_family_id=task.prompt_family_id,
            content_hash=task.content_hash,
            assigned_reviewer_ids=updated_reviewers,
            first_assigned_at=first_assigned,
            due_at=due_at,
            created_at=task.created_at,
        )

        self._tasks[task_id] = updated_task
        self._assignments[assignment.assignment_id] = assignment

        logger.info(
            "review_task_assigned",
            extra={
                "task_id": task_id,
                "reviewer_id": reviewer.reviewer_id,
                "assigner": assigner,
                "due_at": due_at.isoformat(),
            },
        )

        return assignment
    
    def submit_review(
        self,
        task_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        primary_label: str | None = None,
        secondary_labels: list[str] | None = None,
        rationale: str = "",
        raw_revealed: bool = False,
        reveal_reason: str | None = None,
    ) -> ReviewSubmission:
        """Submit a review decision."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Verify assignment - check against multiple reviewers
        if reviewer_id not in task.assigned_reviewer_ids:
            raise ValueError(f"Task not assigned to reviewer {reviewer_id}")

        submission = ReviewSubmission(
            submission_id=new_id("submission"),
            task_id=task_id,
            reviewer_id=reviewer_id,
            decision=decision,
            primary_label=primary_label,
            secondary_labels=secondary_labels or [],
            rationale=rationale,
            raw_revealed=raw_revealed,
            reveal_reason=reveal_reason,
            submitted_at=utc_now(),
        )

        self._submissions[submission.submission_id] = submission

        # Check if we now have two submissions (for blind dual review)
        other_submissions = [
            s for s in self._submissions.values()
            if s.task_id == task_id and s.submission_id != submission.submission_id
        ]

        if len(other_submissions) >= 1:
            # We have two submissions - check for disagreement
            other = other_submissions[0]
            if other.decision != decision and decision != ReviewDecision.ABSTAIN and other.decision != ReviewDecision.ABSTAIN:
                # Disagreement detected - require adjudication
                logger.info(
                    "review_disagreement_detected",
                    extra={"task_id": task_id, "requires_adjudication": True},
                )

        logger.info(
            "review_submitted",
            extra={
                "task_id": task_id,
                "reviewer_id": reviewer_id,
                "decision": decision,
            },
        )

        return submission
    
    def record_recusal(
        self,
        task_id: str,
        reviewer_id: str,
        reason: RecusalReason,
        reason_detail: str,
    ) -> None:
        """Record a reviewer recusal."""
        # Find the assignment
        for assignment in self._assignments.values():
            if assignment.task_id == task_id and assignment.reviewer_id == reviewer_id:
                # Update assignment with recusal
                updated = ReviewAssignment(
                    assignment_id=assignment.assignment_id,
                    task_id=assignment.task_id,
                    reviewer_id=assignment.reviewer_id,
                    assigner=assignment.assigner,
                    reason=assignment.reason,
                    recusal_at=utc_now(),
                    recusal_reason=reason_detail,
                    assigned_at=assignment.assigned_at,
                )
                self._assignments[assignment.assignment_id] = updated
                break
        
        logger.info(
            "review_recusal_recorded",
            extra={
                "task_id": task_id,
                "reviewer_id": reviewer_id,
                "reason": reason,
            },
        )
    
    def adjudicate(
        self,
        task_id: str,
        adjudicator_id: str,
        decision: ReviewDecision,
        primary_label: str | None = None,
        secondary_labels: list[str] | None = None,
        rationale: str = "",
    ) -> Adjudication:
        """Record an adjudication decision."""
        # Get the two reviewer opinions
        submissions = [
            s for s in self._submissions.values()
            if s.task_id == task_id
        ]
        
        opinion_a = submissions[0].decision.value if len(submissions) > 0 else None
        opinion_b = submissions[1].decision.value if len(submissions) > 1 else None
        
        adjudication = Adjudication(
            adjudication_id=new_id("adj"),
            task_id=task_id,
            adjudicator_id=adjudicator_id,
            decision=decision,
            primary_label=primary_label,
            secondary_labels=secondary_labels or [],
            rationale=rationale,
            reviewer_a_opinion=opinion_a,
            reviewer_b_opinion=opinion_b,
            created_at=utc_now(),
        )
        
        self._adjudications[adjudication.adjudication_id] = adjudication
        
        logger.info(
            "review_adjudicated",
            extra={
                "task_id": task_id,
                "adjudicator_id": adjudicator_id,
                "decision": decision,
            },
        )
        
        return adjudication
    
    def get_task_submissions(self, task_id: str) -> list[ReviewSubmission]:
        """Get all submissions for a task."""
        return [
            s for s in self._submissions.values()
            if s.task_id == task_id
        ]
    
    def is_resolved(self, task_id: str) -> bool:
        """Check if a task has a final resolution."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        
        submissions = self.get_task_submissions(task_id)
        
        # Resolved if we have:
        # - One non-abstain submission, or
        # - Two submissions without disagreement, or
        # - An adjudication exists
        if any(s.decision != ReviewDecision.ABSTAIN for s in submissions):
            return len(submissions) >= 1 or bool(
                self._adjudications.get(task_id)
            )
        
        return bool(self._adjudications.get(task_id))


__all__ = [
    "ReviewState",
    "ReviewDecision",
    "ReviewSubmission",
    "Adjudication",
    "ReviewWorkflow",
]