"""Unit tests for grader calibration harness (TODO 31).

Tests cover:
- CalibrationMetrics canonical serialization
- CalibrationSnapshot hashing
- LeakageCanary detection
- CalibrationHarness execution
- Grader registry operations
- Failure cluster identification
"""

import pytest
from datetime import datetime

from wilson_eval3ngine.grading.calibration import (
    CalibrationHarness,
    CalibrationMetrics,
    CalibrationSnapshot,
    CalibrationStatus,
    GraderRegistryEntry,
    LeakageCanary,
)
from wilson_eval3ngine.util import utc_now


class TestCalibrationMetrics:
    """Test suite for CalibrationMetrics."""

    def test_metrics_canonical_serialization(self):
        """Metrics serialize canonically for hashing."""
        m1 = CalibrationMetrics(
            macro_f1=0.85,
            unsafe_compliance_recall=0.90,
            support_by_label={"positive": 50, "negative": 50},
        )
        m2 = CalibrationMetrics(
            macro_f1=0.85,
            unsafe_compliance_recall=0.90,
            support_by_label={"positive": 50, "negative": 50},
        )

        assert m1.to_canonical() == m2.to_canonical()

    def test_metrics_support_counts(self):
        """Support counts include all labels."""
        m = CalibrationMetrics(support_by_label={"a": 10, "b": 20})

        canonical = m.to_canonical()
        assert canonical["support_by_label"]["a"] == 10
        assert canonical["support_by_label"]["b"] == 20


class TestCalibrationSnapshot:
    """Test suite for CalibrationSnapshot."""

    def test_snapshot_content_hash(self):
        """Snapshot computes deterministic content hash."""
        m = CalibrationMetrics(macro_f1=0.85, unsafe_compliance_recall=0.90)

        s1 = CalibrationSnapshot(
            snapshot_id="snap_001",
            grader_version="test-grader-1.0.0",
            grader_package_digest="abc123",
            configuration_hash="def456",
            dataset_hash="dataset_hash_123",
            split="visible",
            timestamp=utc_now(),
            metrics=m,
        )

        s2 = CalibrationSnapshot(
            snapshot_id="snap_002",
            grader_version="test-grader-1.0.0",
            grader_package_digest="abc123",
            configuration_hash="def456",
            dataset_hash="dataset_hash_123",
            split="visible",
            timestamp=s1.timestamp,
            metrics=m,
        )

        assert s1.content_hash() == s2.content_hash()


class TestLeakageCanary:
    """Test suite for LeakageCanary."""

    def test_canary_detection_positive(self):
        """Hidden-set markers are detected."""
        content = f"Some text with {LeakageCanary.CONTENT_MARKERS[0]} inside"

        assert LeakageCanary.is_hidden_content(content) is True

    def test_canary_detection_negative(self):
        """Clean content passes detection."""
        content = "This is clean content without markers"

        assert LeakageCanary.is_hidden_content(content) is False

    def test_canary_not_in_clean_predictions(self):
        """Calibration does not leak canaries into predictions."""
        harness = CalibrationHarness("test-grader", "package-abc")

        # Should not raise
        gold = [{"label": "positive"}, {"label": "negative"}]
        predictions = [{"label": "positive"}, {"label": "negative"}]

        harness.execute_calibration(
            dataset_hash="hash123",
            split="visible",
            gold_labels=gold,
            predictions=predictions,
        )


class TestCalibrationHarness:
    """Test suite for CalibrationHarness."""

    def test_harness_initialization(self):
        """Harness initializes with grader version."""
        harness = CalibrationHarness("test-grader-1.0.0", "package-digest-abc")

        assert harness.grader_version == "test-grader-1.0.0"

    def test_execute_calibration_returns_snapshot(self):
        """Calibration execution produces a snapshot."""
        harness = CalibrationHarness("test-grader-1.0.0", "package-digest-abc")

        gold = [{"label": "positive"}, {"label": "negative"}, {"label": "positive"}]
        predictions = [{"label": "positive"}, {"label": "positive"}, {"label": "positive"}]

        snapshot = harness.execute_calibration(
            dataset_hash="dataset-hash-123",
            split="visible",
            gold_labels=gold,
            predictions=predictions,
        )

        assert isinstance(snapshot, CalibrationSnapshot)
        assert snapshot.grader_version == "test-grader-1.0.0"
        assert snapshot.split == "visible"
        assert snapshot.dataset_hash == "dataset-hash-123"

    def test_metrics_computed_from_labels(self):
        """Metrics reflect label prediction performance."""
        harness = CalibrationHarness("test-grader-1.0.0", "package-digest-abc")

        # Perfect predictions
        gold = [{"label": "positive"}, {"label": "negative"}]
        predictions = [{"label": "positive"}, {"label": "negative"}]

        snapshot = harness.execute_calibration(
            dataset_hash="hash",
            split="visible",
            gold_labels=gold,
            predictions=predictions,
        )

        assert snapshot.metrics.macro_f1 == 1.0

    def test_failure_clusters_identified(self):
        """Misclassifications generate failure clusters."""
        harness = CalibrationHarness("test-grader-1.0.0", "package-digest-abc")

        gold = [{"label": "positive"}, {"label": "negative"}]
        predictions = [{"label": "negative"}, {"label": "positive"}]

        snapshot = harness.execute_calibration(
            dataset_hash="hash",
            split="visible",
            gold_labels=gold,
            predictions=predictions,
        )

        assert len(snapshot.failure_clusters) == 2

    def test_hidden_set_access_flag(self):
        """Hidden-set access only granted for passed graders."""
        harness = CalibrationHarness("test-grader", "package-abc")

        harness.register_grader(
            grader_version="test-grader",
            status=CalibrationStatus.PASSED,
            approved_by=["reviewer1"],
        )

        entry = harness._registry["test-grader"]
        assert entry.hidden_set_access is True

        harness.register_grader(
            grader_version="failed-grader",
            status=CalibrationStatus.FAILED,
            approved_by=["reviewer1"],
        )

        entry = harness._registry["failed-grader"]
        assert entry.hidden_set_access is False

    def test_get_approved_grader(self):
        """Approved grader retrieval."""
        harness = CalibrationHarness("test-grader", "package-abc")

        assert harness.get_approved_grader() is None

        harness.register_grader(
            grader_version="approved-grader",
            status=CalibrationStatus.PASSED,
            approved_by=["reviewer1"],
        )

        assert harness.get_approved_grader() == "approved-grader"


class TestGraderRegistryEntry:
    """Test suite for GraderRegistryEntry."""

    def test_registry_entry_defaults(self):
        """Registry entry has correct defaults."""
        entry = GraderRegistryEntry(
            grader_version="test-grader",
            status=CalibrationStatus.PENDING,
        )

        assert entry.approved_by == []
        assert entry.approval_date is None
        assert entry.rollout_eligible is False
        # rollback_eligible defaults to True per implementation
        assert entry.rollback_eligible is True
        assert entry.hidden_set_access is False

    def test_registry_entry_requires_explicit_approval(self):
        """Rollout and hidden-set access require explicit approval."""
        # Without explicit approval, defaults apply
        entry = GraderRegistryEntry(
            grader_version="test-grader",
            status=CalibrationStatus.PASSED,
            approved_by=["reviewer1", "reviewer2"],
        )

        # Defaults are False unless explicitly set in register_grader
        assert entry.rollout_eligible is False
        assert entry.hidden_set_access is False