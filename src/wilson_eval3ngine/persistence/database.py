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


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            database_path = Path(url.removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, future=True, connect_args=connect_args)
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
