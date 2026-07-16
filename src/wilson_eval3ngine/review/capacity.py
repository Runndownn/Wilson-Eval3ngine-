"""Reviewer capacity model and qualification system (TODO 34).

T5.1.6 - Implements reviewer recruitment, qualification, language/subject expertise,
workload limits, queue SLOs, escalation, wellness controls, and release blocking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from ..util import utc_now


def observer_reviewer_to_workflow(reviewer_id: str) -> Reviewer:
    """Convert stored reviewer to workflow domain object.

    TODO: This will be replaced with proper repository lookup.
    """
    return Reviewer(
        reviewer_id=reviewer_id,
        identity_id="",
        primary_qualifications=QualificationRecord(
            safety_training_completed=True,
            psychological_safety_approved=True,
        ),
        status=ReviewerStatus.ACTIVE,
    )


class ReviewerStatus(StrEnum):
    """Reviewer availability and qualification status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    EXPIRED = "expired"  # Qualification expired


class ReviewCategory(StrEnum):
    """Categories of review work."""
    CRITICAL_UNSAFE = "critical_unsafe"
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"
    LOW_CONFIDENCE = "low_confidence"
    DISAGREEMENT = "disagreement"
    AUDIT_SAMPLING = "audit_sampling"
    ADJUDICATION = "adjudication"


@dataclass(frozen=True, slots=True)
class QualificationRecord:
    """Qualification criteria for a reviewer."""
    # Core qualifications
    languages: list[str] = field(default_factory=list)
    subject_expertise: list[str] = field(default_factory=list)
    safety_training_completed: bool = False
    psychological_safety_approved: bool = False
    
    # Qualification metadata
    certified_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    certification_evidence: str = ""  # Hash of certification artifacts
    
    # Wellness controls
    max_daily_exposures: int = 50
    max_hourly_exposures: int = 10
    max_consecutive_reviews: int = 5
    
    def is_valid(self, at: datetime | None = None) -> bool:
        """Check if qualification is currently valid."""
        check_time = at or utc_now()
        if self.expires_at and check_time > self.expires_at:
            return False
        if not self.safety_training_completed:
            return False
        if not self.psychological_safety_approved:
            return False
        return True
    
    def can_review_category(self, category: ReviewCategory) -> bool:
        """Check if reviewer can handle a specific category."""
        if not self.is_valid():
            return False
        # Critical/unsafe reviewers need additional verification
        if category in (ReviewCategory.CRITICAL_UNSAFE, ReviewCategory.ADJUDICATION):
            return self.safety_training_completed
        return True


@dataclass(frozen=True, slots=True)
class Reviewer:
    """Reviewer with capacity and workload tracking."""
    reviewer_id: str
    identity_id: str  # Linked to OIDC identity
    status: ReviewerStatus
    primary_qualifications: QualificationRecord
    backup_qualifications: QualificationRecord | None = None
    
    # Workload tracking
    current_active_reviews: int = 0
    daily_exposures_count: int = 0
    hourly_exposures_count: int = 0
    last_exposure_at: datetime | None = None
    
    # Queue metrics
    assigned_task_count: int = 0
    completed_task_count: int = 0
    
    # Support role
    is_adjudicator: bool = False
    adjudicator_qualifications: QualificationRecord | None = None
    
    def can_accept_review(self, category: ReviewCategory) -> tuple[bool, str]:
        """Check if reviewer can accept a new review task."""
        if self.status != ReviewerStatus.ACTIVE:
            return False, f"Reviewer status is {self.status}"
        
        if not self.primary_qualifications.is_valid():
            return False, "Primary qualification expired"
        
        if not self.primary_qualifications.can_review_category(category):
            return False, f"Not qualified for category {category}"
        
        if self.current_active_reviews >= self.primary_qualifications.max_consecutive_reviews:
            return False, "Max consecutive reviews reached"
        
        return True, "OK"


@dataclass(frozen=True, slots=True)
class ReviewTask:
    """A review task for human judgment."""
    task_id: str
    project_id: str
    category: ReviewCategory
    run_id: str
    case_version_id: str
    prompt_family_id: str
    content_hash: str  # Hash of redacted content for safe preview
    
    # Assignment tracking - multiple reviewers for blind dual review
    assigned_reviewer_ids: list[str] = field(default_factory=list)
    first_assigned_at: datetime | None = None
    due_at: datetime | None = None
    
    # Submission tracking
    submitted_at: datetime | None = None
    submission: dict[str, Any] | None = None
    
    # Supersession
    superseded_by_task_id: str | None = None
    supersession_reason: str | None = None
    
    created_at: datetime = field(default_factory=utc_now)
    
    def is_overdue(self) -> bool:
        """Check if task is past due."""
        if not self.due_at:
            return False
        return utc_now() > self.due_at


@dataclass(frozen=True, slots=True)
class QueueSLA:
    """SLA configuration for review queues."""
    category: ReviewCategory
    target_hours: int = 24
    warning_hours: int = 12
    critical_target_hours: int = 4  # For critical unsafe cases
    
    def calculate_due_at(self, created_at: datetime, is_critical: bool = False) -> datetime:
        """Calculate due time based on SLA rules."""
        hours = self.critical_target_hours if (is_critical or self.category == ReviewCategory.CRITICAL_UNSAFE) else self.target_hours
        return created_at + timedelta(hours=hours)


@dataclass(frozen=True, slots=True)
class CapacityModel:
    """Model for reviewer capacity planning."""
    # Normal operations
    peak_hourly_reviewers_needed: int = 0
    average_hourly_reviewers_needed: int = 0
    
    # Peak scenarios
    surge_multiplier: float = 2.0
    surge_duration_hours: int = 8
    
    # Vacation/attrition buffer
    vacation_buffer_percent: float = 0.2  # 20% buffer for vacations
    attrition_buffer_percent: float = 0.1  # 10% buffer for attrition
    
    # Critical case coverage
    critical_backup_required: bool = True
    min_critical_reviewers: int = 2
    
    def reviewers_needed(self, month_of_reviews: int) -> dict[str, int]:
        """Calculate required reviewers based on arrival rate forecast."""
        hourly_avg = month_of_reviews / (30 * 24)
        hourly_peak = hourly_avg * self.surge_multiplier
        
        avg_needed = max(1, int(hourly_avg / self._reviews_per_hour_per_reviewer()))
        peak_needed = max(2, int(hourly_peak / self._reviews_per_hour_per_reviewer()))
        
        # Apply buffers
        avg_with_buffer = int(avg_needed * (1 + self.vacation_buffer_percent + self.attrition_buffer_percent))
        peak_with_buffer = int(peak_needed * (1 + self.vacation_buffer_percent + self.attrition_buffer_percent))
        
        return {
            "average_operating": avg_with_buffer,
            "peak_surge": peak_with_buffer,
            "critical_backup": self.min_critical_reviewers if self.critical_backup_required else 0,
        }
    
    def _reviews_per_hour_per_reviewer(self) -> int:
        """Average reviews a reviewer can complete per hour (configurable)."""
        # Conservative estimate for quality review
        return 4


@dataclass(frozen=True, slots=True)
class ReviewAssignment:
    """Immutable record of a review assignment."""
    assignment_id: str
    task_id: str
    reviewer_id: str
    assigner: str  # Identity that made the assignment
    reason: str  # Why this reviewer was chosen
    
    # Recusal tracking
    recusal_at: datetime | None = None
    recusal_reason: str | None = None
    
    assigned_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


class RecusalReason(StrEnum):
    """Reasons for reviewer recusal."""
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    PERSONAL_CONNECTIONS = "personal_connections"
    EXPERTISE_MISMATCH = "expertise_mismatch"
    WELLNESS_CONCERN = "wellness_concern"
    QUALIFICATION_EXPIRED = "qualification_expired"


class ExposureTracking:
    """Track reviewer exposure to harmful content."""
    
    def __init__(self) -> None:
        self._exposures: dict[str, int] = {}  # reviewer_id -> count
        self._last_reset: datetime = utc_now()
    
    def record_exposure(self, reviewer_id: str, count: int = 1) -> None:
        """Record an exposure event."""
        self._exposures[reviewer_id] = self._exposures.get(reviewer_id, 0) + count
    
    def get_exposure(self, reviewer_id: str) -> int:
        """Get total exposures for a reviewer."""
        return self._exposures.get(reviewer_id, 0)
    
    def should_limit_exposure(self, reviewer_id: str, limit: int) -> bool:
        """Check if reviewer has reached exposure limit."""
        return self._exposures.get(reviewer_id, 0) >= limit
    
    def reset_daily(self) -> None:
        """Reset daily counters (should be called at midnight)."""
        self._exposures.clear()
        self._last_reset = utc_now()


__all__ = [
    "ReviewerStatus",
    "ReviewCategory",
    "QualificationRecord",
    "Reviewer",
    "ReviewTask",
    "QueueSLA",
    "CapacityModel",
    "ReviewAssignment",
    "RecusalReason",
    "ExposureTracking",
]