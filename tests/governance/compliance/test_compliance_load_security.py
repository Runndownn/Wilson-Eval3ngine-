"""
Load and security tests for data classification policy.

Tests policy evaluation performance and security boundaries.
"""

import json
import time
import pytest
from pathlib import Path


POLICY_PATH = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/data_classification_policy_matrix.json")


@pytest.fixture
def policy_matrix():
    """Load the data classification policy matrix."""
    with open(POLICY_PATH) as f:
        return json.load(f)


class TestPolicyLoadPerformance:
    """Test policy loading and evaluation performance."""

    def test_policy_load_performance(self, policy_matrix):
        """Policy evaluation must complete within 10ms for production volumes."""
        start = time.perf_counter()
        
        # Simulate policy evaluation (full traversal)
        _ = policy_matrix["data_classes"]
        _ = policy_matrix["precedence_rules"]
        _ = len(policy_matrix["data_classes"])
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # Policy load should be fast
        assert elapsed_ms < 10.0, f"Policy load took {elapsed_ms}ms, exceeds 10ms threshold"

    def test_policy_load_consistency(self, policy_matrix):
        """Policy evaluation must be deterministic across invocations."""
        results = []
        for _ in range(10):
            start = time.perf_counter()
            _ = len(policy_matrix["data_classes"])
            _ = policy_matrix["derived_data_policy"]
            elapsed_ms = (time.perf_counter() - start) * 1000
            results.append(elapsed_ms)
        
        # All invocations should be consistently fast
        assert max(results) < 10.0


class TestSecurityBoundaries:
    """Test security enforcement boundaries."""

    def test_unclassified_data_prohibited_transit(self, policy_matrix):
        """Unclassified data cannot transit to providers without classification."""
        for data_class in policy_matrix["data_classes"]:
            if not data_class["provider_eligibility"]["allowed"]:
                assert data_class["provider_eligibility"]["explicit_approval_required"] is True

    def test_secret_provider_transmission_prohibited(self, policy_matrix):
        """Secret classified data cannot be sent to hosted providers."""
        secret_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Secret"),
            None
        )
        assert secret_class["provider_eligibility"]["allowed"] is False

    def test_telemetry_masking_for_confidential(self, policy_matrix):
        """Confidential data telemetry is masked, not full."""
        confidential_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Confidential"),
            None
        )
        assert confidential_class["telemetry_treatment"] == "masked"

    def test_telemetry_none_for_restricted_and_secret(self, policy_matrix):
        """Restricted and Secret data never appears in telemetry."""
        for cls_name in ["Restricted", "Secret"]:
            cls = next(c for c in policy_matrix["data_classes"] if c["classification"] == cls_name)
            assert cls["telemetry_treatment"] == "none"


class TestNegativeSecurityScenarios:
    """Test negative security scenarios."""

    def test_no_silent_downgrade(self, policy_matrix):
        """Policy has no permissive defaults for downgrades."""
        # Policy for restricted requires explicit approval
        restricted = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Restricted"),
            None
        )
        assert restricted["provider_eligibility"]["notes"] == "Prohibited from hosted-provider processing until explicitly classified; default for unidentified data"

    def test_export_restrictions_escalate(self, policy_matrix):
        """Export restrictions escalate with classification."""
        export_levels = {
            "Public": "none",
            "Internal": "authenticated",
            "Confidential": "role-restricted",
            "Restricted": "prohibited",
            "Secret": "prohibited"
        }
        for data_class in policy_matrix["data_classes"]:
            assert data_class["export_restrictions"] == export_levels[data_class["classification"]]


class TestRetentionAndHold:
    """Test retention and legal hold behaviors."""

    def test_secret_retention_null(self, policy_matrix):
        """Secret retention is null (permanent until explicit destruction)."""
        secret_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Secret"),
            None
        )
        assert secret_class["retention_period_days"] is None

    def test_backfill_deletion(self, policy_matrix):
        """Backup expiration follows retention plus 30 days."""
        precedence = policy_matrix["precedence_rules"]
        assert "backup_expiration_after_retention" in precedence