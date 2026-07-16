"""Unit tests for reviewer capacity model (TODO 34).

Tests cover:
- QualificationRecord validation and expiry
- Reviewer qualification checking
- CapacityModel forecasting
- ExposureTracking limits
- ReviewTask and QueueSLA
"""

from datetime import datetime, timedelta

from wilson_eval3ngine.review.capacity import (
    CapacityModel,
    ExposureTracking,
    QualificationRecord,
    QueueSLA,
    ReviewCategory,
    ReviewTask,
    Reviewer,
    ReviewerStatus,
)
from wilson_eval3ngine.util import utc_now


class TestQualificationRecord:
    """Tests for QualificationRecord."""

    def test_valid_qualification(self):
        """Active qualification is valid."""
        q = QualificationRecord(
            languages=["en", "es"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        assert q.is_valid() is True

    def test_expired_qualification(self):
        """Expired qualification is invalid."""
        from datetime import timezone
        q = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert q.is_valid() is False

    def test_missing_safety_training(self):
        """Missing safety training invalidates qualification."""
        q = QualificationRecord(
            languages=["en"],
            safety_training_completed=False,
            psychological_safety_approved=True,
        )
        assert q.is_valid() is False

    def test_can_review_critical_category(self):
        """Qualified reviewer can handle critical cases."""
        q = QualificationRecord(
            languages=["en"],
            subject_expertise=["safety"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        assert q.can_review_category(ReviewCategory.CRITICAL_UNSAFE) is True

    def test_can_review_critical_without_training(self):
        """Without safety training, cannot review critical cases."""
        q = QualificationRecord(
            languages=["en"],
            safety_training_completed=False,
            psychological_safety_approved=True,
        )
        assert q.can_review_category(ReviewCategory.CRITICAL_UNSAFE) is False


class TestReviewer:
    """Tests for Reviewer."""

    def test_active_reviewer_can_accept(self):
        """Active qualified reviewer can accept reviews."""
        q = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_001",
            identity_id="user_abc",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=q,
        )
        can_accept, reason = reviewer.can_accept_review(ReviewCategory.AMBIGUITY_RESOLUTION)
        assert can_accept is True
        assert reason == "OK"

    def test_inactive_reviewer_cannot_accept(self):
        """Inactive reviewer cannot accept reviews."""
        q = QualificationRecord(
            languages=["en"],
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_002",
            identity_id="user_def",
            status=ReviewerStatus.INACTIVE,
            primary_qualifications=q,
        )
        can_accept, reason = reviewer.can_accept_review(ReviewCategory.AMBIGUITY_RESOLUTION)
        assert can_accept is False
        assert "status" in reason.lower()

    def test_max_consecutive_reviews(self):
        """Reviewer cannot exceed max consecutive reviews."""
        q = QualificationRecord(
            languages=["en"],
            max_consecutive_reviews=3,
            safety_training_completed=True,
            psychological_safety_approved=True,
        )
        reviewer = Reviewer(
            reviewer_id="rev_003",
            identity_id="user_ghi",
            status=ReviewerStatus.ACTIVE,
            primary_qualifications=q,
            current_active_reviews=3,
        )
        can_accept, reason = reviewer.can_accept_review(ReviewCategory.AMBIGUITY_RESOLUTION)
        assert can_accept is False
        assert "max consecutive" in reason.lower()


class TestQueueSLA:
    """Tests for QueueSLA."""

    def test_critical_sla_shorter(self):
        """Critical cases have shorter SLA."""
        critical_sla = QueueSLA(category=ReviewCategory.CRITICAL_UNSAFE)
        regular_sla = QueueSLA(category=ReviewCategory.AMBIGUITY_RESOLUTION)
        
        created = utc_now()
        critical_due = critical_sla.calculate_due_at(created, is_critical=True)
        regular_due = regular_sla.calculate_due_at(created, is_critical=False)
        
        # Critical should have shorter due time
        assert critical_due < regular_due

    def test_default_sla(self):
        """Default SLA is 24 hours."""
        sla = QueueSLA(category=ReviewCategory.AUDIT_SAMPLING)
        created = utc_now()
        due = sla.calculate_due_at(created)
        
        expected_due = created + timedelta(hours=24)
        assert due == expected_due


class TestCapacityModel:
    """Tests for CapacityModel forecasting."""

    def test_reviewers_needed_calculation(self):
        """Capacity model calculates required reviewers."""
        model = CapacityModel(
            surge_multiplier=1.5,
            vacation_buffer_percent=0.1,
            attrition_buffer_percent=0.05,
        )
        
        # 1440 reviews per month = ~2 reviews per hour
        result = model.reviewers_needed(1440)
        
        assert result["average_operating"] >= 1
        assert result["peak_surge"] >= result["average_operating"]
        assert result["critical_backup"] >= 0

    def test_high_volume_calculates_multiple_reviewers(self):
        """High volume requires multiple reviewers."""
        model = CapacityModel(
            surge_multiplier=1.0,
            vacation_buffer_percent=0.0,
            attrition_buffer_percent=0.0,
        )
        
        # 2880 reviews per month = ~48 reviews/day = ~2/hour
        result = model.reviewers_needed(2880)
        
        assert result["average_operating"] >= 1


class TestExposureTracking:
    """Tests for ExposureTracking."""

    def test_record_and_get_exposure(self):
        """Exposures are tracked correctly."""
        tracker = ExposureTracking()
        
        tracker.record_exposure("rev_001")
        tracker.record_exposure("rev_001", count=3)
        
        assert tracker.get_exposure("rev_001") == 4

    def test_multiple_reviewers_independent(self):
        """Each reviewer's exposure is tracked independently."""
        tracker = ExposureTracking()
        
        tracker.record_exposure("rev_001", count=5)
        tracker.record_exposure("rev_002", count=3)
        
        assert tracker.get_exposure("rev_001") == 5
        assert tracker.get_exposure("rev_002") == 3

    def test_limit_checking(self):
        """Exposure limits are enforced."""
        tracker = ExposureTracking()
        
        tracker.record_exposure("rev_001", count=10)
        
        assert tracker.should_limit_exposure("rev_001", limit=10) is True
        assert tracker.should_limit_exposure("rev_001", limit=15) is False

    def test_reset_clears_counts(self):
        """Daily reset clears exposure counts."""
        tracker = ExposureTracking()
        
        tracker.record_exposure("rev_001", count=10)
        tracker.reset_daily()
        
        assert tracker.get_exposure("rev_001") == 0


class TestReviewTask:
    """Tests for ReviewTask."""

    def test_task_creation(self):
        """Review task is created with required fields."""
        task = ReviewTask(
            task_id="task_001",
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_abc",
        )
        
        assert task.task_id == "task_001"
        assert task.category == ReviewCategory.CRITICAL_UNSAFE
        assert task.created_at is not None

    def test_overdue_detection(self):
        """Overdue tasks are detected."""
        past_time = utc_now() - timedelta(hours=2)
        task = ReviewTask(
            task_id="task_002",
            project_id="proj_001",
            category=ReviewCategory.CRITICAL_UNSAFE,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_abc",
            due_at=past_time,
        )
        
        assert task.is_overdue() is True

    def test_not_overdue_when_no_due(self):
        """Task without due_at is never overdue."""
        task = ReviewTask(
            task_id="task_003",
            project_id="proj_001",
            category=ReviewCategory.AMBIGUITY_RESOLUTION,
            run_id="run_abc",
            case_version_id="case_123",
            prompt_family_id="family_xyz",
            content_hash="sha256_abc",
        )
        
        assert task.is_overdue() is False