from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ..domain.contracts import (
    Classification as ClassificationContract,
    GateDecision as GateDecisionContract,
    MetricSnapshot as MetricSnapshotContract,
    RunResult,
)
from ..domain.enums import ExperimentState
from ..util import utc_now


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ExperimentRow(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lane: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class RunRow(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("experiment_id", "logical_key", name="uq_run_logical"),
        Index("ix_runs_project_experiment_state", "project_id", "experiment_id", "state"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    logical_key: Mapped[str] = mapped_column(String(64), nullable=False)
    case_version_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_family_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_config_id: Mapped[str] = mapped_column(String(255), nullable=False)
    repetition_index: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_treatment: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    request_artifact_hash: Mapped[str | None] = mapped_column(String(64))
    response_artifact_hash: Mapped[str | None] = mapped_column(String(64))
    reliability_error: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ClassificationRow(Base):
    __tablename__ = "classifications"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    primary_label: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    superseded_by_id: Mapped[str | None] = mapped_column(String(96))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class MetricSnapshotRow(Base):
    __tablename__ = "metric_snapshots"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_config_id: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class GateDecisionRow(Base):
    __tablename__ = "gate_decisions"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_config_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_state_available", "state", "available_at"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leased_by: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


# Review and Governance ORM Models (TODO 34-36)

class QualificationRow(Base):
    __tablename__ = "qualifications"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    reviewer_id: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    subject_expertise: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    safety_training_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    psychological_safety_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    max_daily_exposures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    max_hourly_exposures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    max_consecutive_reviews: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    certified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    certification_evidence: Mapped[str | None] = mapped_column(String(255))


class ReviewerRow(Base):
    __tablename__ = "reviewers"
    __table_args__ = (
        Index("ix_reviewers_project_id", "project_id"),
        Index("ix_reviewers_identity_id", "identity_id"),
        Index("ix_reviewers_status", "status"),
        Index("ix_reviewers_adjudicator", "is_adjudicator"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    identity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="inactive")
    qualification_id: Mapped[str] = mapped_column(
        ForeignKey("qualifications.id", ondelete="RESTRICT"), nullable=False
    )
    is_adjudicator: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    current_active_reviews: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    daily_exposures_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    hourly_exposures_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_exposure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_task_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed_task_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ReviewTaskRow(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (
        Index("ix_review_tasks_project_id", "project_id"),
        Index("ix_review_tasks_category", "category"),
        Index("ix_review_tasks_due_at", "due_at"),
        Index("ix_review_tasks_state", "state"),
        Index("ix_review_tasks_run_id", "run_id"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    case_version_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_family_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_reviewer_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    first_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    superseded_by_task_id: Mapped[str | None] = mapped_column(String(96))
    superseded_reason: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ReviewAssignmentRow(Base):
    __tablename__ = "review_assignments"
    __table_args__ = (
        Index("ix_assignments_task_id", "task_id"),
        Index("ix_assignments_reviewer_id", "reviewer_id"),
        Index("ix_assignments_recusal", "recusal_at"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False
    )
    assigner: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    recusal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recusal_reason: Mapped[str | None] = mapped_column(String(255))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewSubmissionRow(Base):
    __tablename__ = "review_submissions"
    __table_args__ = (
        Index("ix_submissions_task_id", "task_id"),
        Index("ix_submissions_reviewer_id", "reviewer_id"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_label: Mapped[str | None] = mapped_column(String(64))
    secondary_labels: Mapped[list[str]] = mapped_column(JSON, server_default="[]")
    rationale: Mapped[str | None] = mapped_column(String)
    raw_revealed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    reveal_reason: Mapped[str | None] = mapped_column(String(255))
    evidence_notes: Mapped[str | None] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AdjudicationRow(Base):
    __tablename__ = "adjudications"
    __table_args__ = (
        Index("ix_adjudications_task_id", "task_id"),
        Index("ix_adjudications_adjudicator_id", "adjudicator_id"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False
    )
    adjudicator_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_label: Mapped[str | None] = mapped_column(String(64))
    secondary_labels: Mapped[list[str]] = mapped_column(JSON, server_default="[]")
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    reviewer_a_opinion: Mapped[str | None] = mapped_column(String(64))
    reviewer_b_opinion: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ThresholdSetRow(Base):
    __tablename__ = "threshold_sets"
    __table_args__ = (
        Index("ix_threshold_sets_project_id", "project_id"),
        Index("ix_threshold_sets_threshold_set_id", "threshold_set_id"),
        UniqueConstraint("threshold_set_id", "version", name="uq_threshold_set_version"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    threshold_set_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    calibration_evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    minimum_prompt_families: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OverrideRow(Base):
    __tablename__ = "overrides"
    __table_args__ = (
        Index("ix_overrides_gate_id", "gate_id"),
        Index("ix_overrides_expires_at", "expires_at"),
        Index("ix_overrides_approver_a", "approver_a"),
        Index("ix_overrides_approver_b", "approver_b"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    gate_id: Mapped[str] = mapped_column(String(96), nullable=False)
    requester: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    approver_a: Mapped[str | None] = mapped_column(String(255))
    approver_b: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compensating_controls: Mapped[list[str]] = mapped_column(JSON, server_default="[]")
    follow_up_ticket: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Database:
    def __init__(
        self,
        url: str,
        *,
        connect_args: dict | None = None,
        poolclass: type | None = None,
    ) -> None:
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            database_path = Path(url.removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)
        if connect_args is None:
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine_kwargs: dict = {"future": True, "connect_args": connect_args}
        if poolclass is not None:
            engine_kwargs["poolclass"] = poolclass
        self.engine = create_engine(url, **engine_kwargs)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=Session,
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_project(self, project_id: str) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(ProjectRow, project_id)
            if row is None:
                session.add(ProjectRow(id=project_id, name=project_id))

    def create_experiment(
        self,
        *,
        experiment_id: str,
        project_id: str,
        name: str,
        lane: str,
        manifest_hash: str,
        manifest_json: dict[str, Any],
    ) -> None:
        with self.database.session() as session, session.begin():
            session.add(
                ExperimentRow(
                    id=experiment_id,
                    project_id=project_id,
                    name=name,
                    lane=lane,
                    state=ExperimentState.RUNNING.value,
                    manifest_hash=manifest_hash,
                    manifest_json=manifest_json,
                )
            )

    def set_experiment_state(
        self,
        experiment_id: str,
        state: ExperimentState,
    ) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(ExperimentRow, experiment_id)
            if row is None:
                raise KeyError(experiment_id)
            row.state = state.value
            row.updated_at = utc_now()

    def create_run(self, run: RunResult) -> None:
        with self.database.session() as session, session.begin():
            session.add(
                RunRow(
                    id=run.run_id,
                    project_id=run.project_id,
                    experiment_id=run.experiment_id,
                    logical_key=run.logical_key,
                    case_version_id=run.case_version_id,
                    prompt_family_id=run.prompt_family_id,
                    model_config_id=run.model_config_id,
                    repetition_index=run.repetition_index,
                    expected_treatment=run.expected_treatment.value,
                    state=run.state.value,
                )
            )

    def update_run(self, run: RunResult) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(RunRow, run.run_id)
            if row is None:
                raise KeyError(run.run_id)
            row.state = run.state.value
            row.request_artifact_hash = run.request_artifact_hash
            row.response_artifact_hash = run.response_artifact_hash
            row.reliability_error = run.reliability_error
            row.updated_at = utc_now()

    def add_classification(
        self,
        *,
        project_id: str,
        classification: ClassificationContract,
    ) -> None:
        with self.database.session() as session, session.begin():
            session.add(
                ClassificationRow(
                    id=classification.classification_id,
                    project_id=project_id,
                    run_id=classification.run_id,
                    primary_label=classification.primary_label.value,
                    confidence=classification.confidence,
                    requires_human_review=classification.requires_human_review,
                    payload_json=classification.model_dump(mode="json"),
                )
            )

    def add_metric_snapshot(
        self,
        *,
        project_id: str,
        snapshot: MetricSnapshotContract,
    ) -> None:
        if not snapshot.snapshot_sha256:
            raise ValueError("metric snapshot must be finalized")
        with self.database.session() as session, session.begin():
            session.add(
                MetricSnapshotRow(
                    id=snapshot.snapshot_id,
                    project_id=project_id,
                    experiment_id=snapshot.experiment_id,
                    model_config_id=snapshot.model_config_id,
                    snapshot_hash=snapshot.snapshot_sha256,
                    payload_json=snapshot.model_dump(mode="json"),
                )
            )

    def add_gate(
        self,
        *,
        project_id: str,
        gate: GateDecisionContract,
    ) -> None:
        with self.database.session() as session, session.begin():
            session.add(
                GateDecisionRow(
                    id=gate.gate_id,
                    project_id=project_id,
                    experiment_id=gate.experiment_id,
                    model_config_id=gate.model_config_id,
                    status=gate.status.value,
                    payload_json=gate.model_dump(mode="json"),
                )
            )

    def get_experiment(self, project_id: str, experiment_id: str) -> dict[str, Any] | None:
        with self.database.session() as session:
            row = session.scalar(
                select(ExperimentRow).where(
                    ExperimentRow.id == experiment_id,
                    ExperimentRow.project_id == project_id,
                )
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "project_id": row.project_id,
                "name": row.name,
                "lane": row.lane,
                "state": row.state,
                "manifest_hash": row.manifest_hash,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }


class ReviewRepository:
    """Persistence methods for review and governance operations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    # Reviewer methods
    def create_reviewer(
        self,
        *,
        reviewer_id: str,
        project_id: str,
        identity_id: str,
        status: str,
        qualification_id: str,
        is_adjudicator: bool = False,
    ) -> None:
        """Create a qualified reviewer."""
        with self.database.session() as session, session.begin():
            session.add(
                ReviewerRow(
                    id=reviewer_id,
                    project_id=project_id,
                    identity_id=identity_id,
                    status=status,
                    qualification_id=qualification_id,
                    is_adjudicator=is_adjudicator,
                )
            )

    def create_qualification(
        self,
        *,
        qualification_id: str,
        reviewer_id: str,
        languages: list[str],
        subject_expertise: list[str],
        safety_training_completed: bool,
        psychological_safety_approved: bool,
        max_daily_exposures: int = 50,
        max_hourly_exposures: int = 10,
        max_consecutive_reviews: int = 5,
        expires_at: datetime | None = None,
        certification_evidence: str = "",
    ) -> None:
        """Create a reviewer qualification record."""
        with self.database.session() as session, session.begin():
            session.add(
                QualificationRow(
                    id=qualification_id,
                    reviewer_id=reviewer_id,
                    languages=languages,
                    subject_expertise=subject_expertise,
                    safety_training_completed=safety_training_completed,
                    psychological_safety_approved=psychological_safety_approved,
                    max_daily_exposures=max_daily_exposures,
                    max_hourly_exposures=max_hourly_exposures,
                    max_consecutive_reviews=max_consecutive_reviews,
                    expires_at=expires_at,
                    certification_evidence=certification_evidence,
                )
            )

    def create_review_task(
        self,
        *,
        task_id: str,
        project_id: str,
        category: str,
        run_id: str,
        case_version_id: str,
        prompt_family_id: str,
        content_hash: str,
    ) -> None:
        """Create a review task for human judgment."""
        with self.database.session() as session, session.begin():
            session.add(
                ReviewTaskRow(
                    id=task_id,
                    project_id=project_id,
                    category=category,
                    run_id=run_id,
                    case_version_id=case_version_id,
                    prompt_family_id=prompt_family_id,
                    content_hash=content_hash,
                )
            )

    def assign_review_task(
        self,
        *,
        assignment_id: str,
        task_id: str,
        reviewer_id: str,
        assigner: str,
        reason: str,
    ) -> None:
        """Record a review task assignment."""
        with self.database.session() as session, session.begin():
            task_row = session.get(ReviewTaskRow, task_id)
            if task_row:
                task_row.assigned_reviewer_ids = list(set(task_row.assigned_reviewer_ids + [reviewer_id]))
                task_row.state = "assigned"
                if task_row.first_assigned_at is None:
                    task_row.first_assigned_at = utc_now()

            session.add(
                ReviewAssignmentRow(
                    id=assignment_id,
                    task_id=task_id,
                    reviewer_id=reviewer_id,
                    assigner=assigner,
                    reason=reason,
                )
            )

    def submit_review(
        self,
        *,
        submission_id: str,
        task_id: str,
        reviewer_id: str,
        decision: str,
        primary_label: str | None = None,
        raw_revealed: bool = False,
        reveal_reason: str | None = None,
        rationale: str = "",
    ) -> None:
        """Record a review submission."""
        with self.database.session() as session, session.begin():
            session.add(
                ReviewSubmissionRow(
                    id=submission_id,
                    task_id=task_id,
                    reviewer_id=reviewer_id,
                    decision=decision,
                    primary_label=primary_label,
                    raw_revealed=raw_revealed,
                    reveal_reason=reveal_reason,
                    rationale=rationale,
                )
            )

    def record_adjudication(
        self,
        *,
        adjudication_id: str,
        task_id: str,
        adjudicator_id: str,
        decision: str,
        primary_label: str | None = None,
        rationale: str = "",
        reviewer_a_opinion: str | None = None,
        reviewer_b_opinion: str | None = None,
    ) -> None:
        """Record an adjudication decision."""
        with self.database.session() as session, session.begin():
            task_row = session.get(ReviewTaskRow, task_id)
            if task_row:
                task_row.state = "resolved"
                task_row.submitted_at = utc_now()

            session.add(
                AdjudicationRow(
                    id=adjudication_id,
                    task_id=task_id,
                    adjudicator_id=adjudicator_id,
                    decision=decision,
                    primary_label=primary_label,
                    rationale=rationale,
                    reviewer_a_opinion=reviewer_a_opinion,
                    reviewer_b_opinion=reviewer_b_opinion,
                )
            )

    def get_unresolved_critical_tasks(self, project_id: str) -> int:
        """Get count of unresolved critical review tasks."""
        from sqlalchemy import func
        with self.database.session() as session:
            count = session.query(func.count(ReviewTaskRow.id)).filter(
                ReviewTaskRow.project_id == project_id,
                ReviewTaskRow.category == "critical_unsafe",
                ReviewTaskRow.state != "resolved",
            ).scalar()
            return count or 0

    def create_threshold_set(
        self,
        *,
        threshold_set_id: str,
        project_id: str,
        version: str,
        owner: str,
        rationale: str,
        calibration_evidence_sha256: str,
        rules: list[dict[str, Any]],
        minimum_prompt_families: int = 30,
    ) -> None:
        """Create a versioned threshold set."""
        with self.database.session() as session, session.begin():
            session.add(
                ThresholdSetRow(
                    id=threshold_set_id,
                    project_id=project_id,
                    threshold_set_id=threshold_set_id,
                    version=version,
                    owner=owner,
                    rationale=rationale,
                    calibration_evidence_sha256=calibration_evidence_sha256,
                    minimum_prompt_families=minimum_prompt_families,
                    rules_json=rules,
                )
            )

    def create_override(
        self,
        *,
        override_id: str,
        gate_id: str,
        requester: str,
        rationale: str,
        scope: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> None:
        """Create an override request."""
        with self.database.session() as session, session.begin():
            session.add(
                OverrideRow(
                    id=override_id,
                    gate_id=gate_id,
                    requester=requester,
                    rationale=rationale,
                    scope_json=scope,
                    expires_at=expires_at,
                )
            )

    def approve_override(
        self,
        *,
        override_id: str,
        approver: str,
        is_first_approver: bool = True,
    ) -> None:
        """Record override approval."""
        with self.database.session() as session, session.begin():
            row = session.get(OverrideRow, override_id)
            if row is None:
                raise KeyError(override_id)
            if is_first_approver:
                row.approver_a = approver
            else:
                row.approver_b = approver
                row.approved_at = utc_now()
