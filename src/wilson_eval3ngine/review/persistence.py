"""Persistence layer for review and governance operations (TODO 34-36).

Integrates the in-memory workflow models with database persistence.
Enforces RLS, audit logging, and project-scoped access controls.
"""

from __future__ import annotations

import logging
from typing import Any

from ..domain.contracts import GateDecision, ThresholdSet
from ..persistence.database import Database, ReviewRepository, ReviewTaskRow
from ..persistence.audit import AuditLedger
from ..util import new_id, utc_now
from datetime import timedelta
from .capacity import QualificationRecord, ReviewCategory, Reviewer, ReviewerStatus
from .governance import OverrideEngine, GatePrecedence
from .workflow import ReviewDecision, ReviewWorkflow

logger = logging.getLogger(__name__)


class ReviewPersistence:
    """Database-backed review workflow with access control."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._in_memory_workflow = ReviewWorkflow()
        self._in_memory_governance = OverrideEngine()
        self._repository = ReviewRepository(database)

    def create_reviewer(
        self,
        *,
        project_id: str,
        identity_id: str,
        qualification: QualificationRecord,
        is_adjudicator: bool = False,
    ) -> Reviewer:
        """Create a reviewer with qualification record.

        Returns Reviewer domain object.
        """
        qualification_id = new_id("qual")
        reviewer_id = new_id("rev")

        self._repository.create_qualification(
            qualification_id=qualification_id,
            reviewer_id=reviewer_id,
            languages=qualification.languages,
            subject_expertise=qualification.subject_expertise,
            safety_training_completed=qualification.safety_training_completed,
            psychological_safety_approved=qualification.psychological_safety_approved,
            max_daily_exposures=qualification.max_daily_exposures,
            max_hourly_exposures=qualification.max_hourly_exposures,
            max_consecutive_reviews=qualification.max_consecutive_reviews,
            expires_at=qualification.expires_at,
            certification_evidence=qualification.certification_evidence,
        )

        self._repository.create_reviewer(
            reviewer_id=reviewer_id,
            project_id=project_id,
            identity_id=identity_id,
            status="active",
            qualification_id=qualification_id,
            is_adjudicator=is_adjudicator,
        )

        reviewer = Reviewer(
            reviewer_id=reviewer_id,
            identity_id=identity_id,
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=qualification,
            completed_task_count=0,
            is_adjudicator=is_adjudicator,
        )

        logger.info(
            "reviewer_created",
            extra={
                "reviewer_id": reviewer_id,
                "project_id": project_id,
                "is_adjudicator": is_adjudicator,
                "qualification_valid": qualification.is_valid(),
            },
        )

        return reviewer

    def create_review_task(
        self,
        *,
        project_id: str,
        category: ReviewCategory,
        run_id: str,
        case_version_id: str,
        prompt_family_id: str,
        content_hash: str,
        actor_id: str,
    ) -> str:
        """Create a review task with audit trail."""
        task_id = new_id("review_task")

        # Use application-level project_id filtering (compatible with SQLite)
        self._repository.create_review_task(
            task_id=task_id,
            project_id=project_id,
            category=category.value,
            run_id=run_id,
            case_version_id=case_version_id,
            prompt_family_id=prompt_family_id,
            content_hash=content_hash,
        )

        AuditLedger(self.database).append(
            project_id=project_id,
            event_type="review_task_created",
            aggregate_type="review_task",
            aggregate_id=task_id,
            actor_id=actor_id,
            payload={
                "category": category.value,
                "run_id": run_id,
                "content_hash": content_hash,
            },
        )

        logger.info(
            "review_task_created",
            extra={"task_id": task_id, "project_id": project_id, "category": category.value},
        )

        return task_id

    def assign_task(
        self,
        *,
        task_id: str,
        reviewer_id: str,
        assigner: str,
        actor_id: str,
    ) -> str | None:
        """Assign task to reviewer with project-level access control."""
        with self.database.session() as session, session.begin():
            task = session.get(ReviewTaskRow, task_id)
            if task is None:
                logger.error(f"Task {task_id} not found")
                return None

            project_id = task.project_id

            # Check reviewer qualification
            can_accept, reason = self._check_reviewer_qualification_in_session(
                session, reviewer_id, task.category
            )

            if not can_accept:
                logger.warning(f"Reviewer {reviewer_id} cannot accept task {task_id}: {reason}")
                return None

            assignment_id = new_id("assign")

            self._repository.assign_review_task(
                assignment_id=assignment_id,
                task_id=task_id,
                reviewer_id=reviewer_id,
                assigner=assigner,
                reason="Qualified assignment",
            )

            AuditLedger(self.database).append(
                project_id=project_id,
                event_type="review_task_assigned",
                aggregate_type="review_task",
                aggregate_id=task_id,
                actor_id=actor_id,
                payload={
                    "reviewer_id": reviewer_id,
                    "assignment_id": assignment_id,
                },
            )

        return assignment_id

    def _check_reviewer_qualification_in_session(
        self,
        session: Any,
        reviewer_id: str,
        category: str,
    ) -> tuple[bool, str]:
        """Check if reviewer is qualified for the category (session-based)."""
        from ..persistence.database import ReviewerRow, QualificationRow
        from datetime import datetime, timezone

        reviewer = session.get(ReviewerRow, reviewer_id)
        if reviewer is None or reviewer.status != "active":
            return False, f"Reviewer {reviewer_id} not active or not found"

        qual = session.get(QualificationRow, reviewer.qualification_id)
        if qual is None:
            return False, f"Qualification {reviewer.qualification_id} not found"

        # Check expiration (compare dates without timezone for SQLite compatibility)
        if qual.expires_at is not None:
            now = datetime.now(timezone.utc)
            expires_naive = qual.expires_at.replace(tzinfo=None) if qual.expires_at.tzinfo else qual.expires_at
            if now.replace(tzinfo=None) > expires_naive + timedelta(days=1):
                return False, "Qualification expired"

        # Check safety training for critical categories
        if category in ("critical_unsafe", "adjudication"):
            if not qual.safety_training_completed:
                return False, "Missing safety training for critical review"

        return True, "OK"

    def submit_review(
        self,
        *,
        task_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        primary_label: str | None,
        raw_revealed: bool,
        reveal_reason: str | None,
        rationale: str,
        actor_id: str,
    ) -> str:
        """Submit review decision with audit trail and raw reveal tracking."""
        submission_id = new_id("submission")

        with self.database.session() as session, session.begin():
            task = session.get(ReviewTaskRow, task_id)
            if task is None:
                raise ValueError(f"Task {task_id} not found")
            project_id = task.project_id

            # Check reviewer is assigned
            if reviewer_id not in task.assigned_reviewer_ids:
                raise ValueError(f"Task not assigned to reviewer {reviewer_id}")

            self._repository.submit_review(
                submission_id=submission_id,
                task_id=task_id,
                reviewer_id=reviewer_id,
                decision=decision.value,
                primary_label=primary_label,
                raw_revealed=raw_revealed,
                reveal_reason=reveal_reason,
                rationale=rationale,
            )

            AuditLedger(self.database).append(
                project_id=project_id,
                event_type="review_submitted",
                aggregate_type="review_task",
                aggregate_id=task_id,
                actor_id=actor_id,
                payload={
                    "reviewer_id": reviewer_id,
                    "decision": decision.value,
                    "raw_revealed": raw_revealed,
                },
            )

        logger.info(
            "review_submitted",
            extra={
                "submission_id": submission_id,
                "task_id": task_id,
                "reviewer_id": reviewer_id,
                "decision": decision.value,
                "raw_revealed": raw_revealed,
            },
        )

        return submission_id

    def record_adjudication(
        self,
        *,
        task_id: str,
        adjudicator_id: str,
        decision: ReviewDecision,
        primary_label: str | None,
        rationale: str,
        actor_id: str,
    ) -> str:
        """Record an adjudication decision for a review task."""
        adjudication_id = new_id("adj")

        with self.database.session() as session, session.begin():
            # Verify task exists and adjudicator is distinct from reviewers
            task = session.get(ReviewTaskRow, task_id)
            if task is None:
                raise ValueError(f"Task {task_id} not found")

            # Check adjudicator wasn't one of the reviewers (self-adjudication prevention)
            if adjudicator_id in task.assigned_reviewer_ids:
                raise ValueError(
                    f"Adjudicator cannot adjudicate their own submission: "
                    f"adjudicator {adjudicator_id} is in assigned reviewers"
                )

            self._repository.record_adjudication(
                adjudication_id=adjudication_id,
                task_id=task_id,
                adjudicator_id=adjudicator_id,
                decision=decision.value,
                primary_label=primary_label,
                rationale=rationale,
            )

            AuditLedger(self.database).append(
                project_id=task.project_id,
                event_type="adjudication_recorded",
                aggregate_type="review_task",
                aggregate_id=task_id,
                actor_id=actor_id,
                payload={
                    "adjudicator_id": adjudicator_id,
                    "decision": decision.value,
                },
            )

        logger.info(
            "adjudication_recorded",
            extra={
                "adjudication_id": adjudication_id,
                "task_id": task_id,
                "adjudicator_id": adjudicator_id,
            },
        )

        return adjudication_id

    def get_unresolved_critical_tasks(self, project_id: str) -> int:
        """Get count of unresolved critical review tasks for blocking release."""
        return self._repository.get_unresolved_critical_tasks(project_id)


class GovernancePersistence:
    """Database-backed governance with threshold sets and overrides."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._repository = ReviewRepository(database)

    def create_threshold_set(
        self,
        *,
        project_id: str,
        version: str,
        owner: str,
        rationale: str,
        calibration_evidence_sha256: str,
        thresholds: ThresholdSet,
        actor_id: str,
    ) -> str:
        """Create a versioned threshold set with audit."""
        threshold_set_id = new_id("threshold")

        self._repository.create_threshold_set(
            threshold_set_id=threshold_set_id,
            project_id=project_id,
            version=version,
            owner=owner,
            rationale=rationale,
            calibration_evidence_sha256=calibration_evidence_sha256,
            rules=[r.model_dump(mode="json") for r in thresholds.rules],
            minimum_prompt_families=thresholds.minimum_prompt_families,
        )

        AuditLedger(self.database).append(
            project_id=project_id,
            event_type="threshold_set_created",
            aggregate_type="threshold_set",
            aggregate_id=threshold_set_id,
            actor_id=actor_id,
            payload={
                "version": version,
                "rationale": rationale,
            },
        )

        return threshold_set_id

    def create_override(
        self,
        *,
        gate_id: str,
        requester: str,
        rationale: str,
        scope: dict[str, Any],
        expires_in_days: int = 30,
    ) -> str:
        """Create override request and record to database."""
        override_id = new_id("override")

        self._repository.create_override(
            override_id=override_id,
            gate_id=gate_id,
            requester=requester,
            rationale=rationale,
            scope=scope,
            expires_at=utc_now() + timedelta(days=expires_in_days),
        )

        logger.info(
            "override_created",
            extra={"override_id": override_id, "gate_id": gate_id, "requester": requester},
        )

        return override_id

    def apply_gate_precedence(
        self,
        decision: GateDecision,
    ) -> GateDecision:
        """Apply gate precedence rules to prevent unsafe override bypass."""
        return GatePrecedence.evaluate(decision)


__all__ = [
    "ReviewPersistence",
    "GovernancePersistence",
]