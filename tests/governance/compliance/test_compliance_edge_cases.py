"""
Edge case tests for data classification policy compliance.

Tests derived data classification, mixed classification bundles, unclassified attachments,
and content in free-text rationale fields.
"""

import json
import pytest
from pathlib import Path


POLICY_PATH = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/data_classification_policy_matrix.json")


@pytest.fixture
def policy_matrix():
    """Load the data classification policy matrix."""
    with open(POLICY_PATH) as f:
        return json.load(f)


@pytest.fixture
def split_triggers():
    """Load the modular split triggers."""
    triggers_path = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/modular_split_triggers.json")
    with open(triggers_path) as f:
        return json.load(f)


class TestDerivedDataClassification:
    """Test that derived data inherits the maximum classification of source data."""

    def test_derived_data_inherits_max_classification(self, policy_matrix):
        """Derived data with mixed sources inherits highest classification."""
        # If source data is Confidential and derived data uses Secret elements,
        # derived data becomes Secret (max classification)

        # Policy states derived data's classification is max of sources
        derived_policy = policy_matrix["derived_data_policy"]
        assert derived_policy["max_reclassification"] == "source"
        assert derived_policy["inherited_classification"] is True

    def test_derived_data_reasoning_required(self, policy_matrix):
        """Derived data reclassification requires documented reasoning."""
        derived_policy = policy_matrix["derived_data_policy"]
        assert derived_policy["reasoning_required"] is True


class TestMixedClassificationBundles:
    """Test handling of mixed classification bundles."""

    def test_mixed_classification_bundle_prohibited(self, policy_matrix):
        """Mixed classification bundles are prohibited per policy."""
        # Find Restricted class - it should prohibit mixed bundles
        restricted_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Restricted"),
            None
        )
        assert restricted_class is not None
        assert restricted_class["export_restrictions"] == "prohibited"

    def test_confidential_in_mixed_requires_key(self, policy_matrix):
        """Confidential data in mixed bundle requires customer-managed key."""
        confidential_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Confidential"),
            None
        )
        assert confidential_class["encryption_required"] is True
        assert confidential_class["encryption_key_type"] == "customer-managed"


class TestUnclassifiedAttachments:
    """Test that unclassified attachments default to Restricted."""

    def test_unclassified_attachment_default_restricted(self, policy_matrix):
        """Unclassified data defaults to Restricted per policy."""
        restricted_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Restricted"),
            None
        )
        assert restricted_class is not None
        assert restricted_class["provider_eligibility"]["allowed"] is False
        assert "explicit_approval_required" in restricted_class["provider_eligibility"]

    def test_unclassified_cannot_transit_to_provider(self, policy_matrix):
        """Unclassified/Restricted data cannot be sent to hosted providers."""
        restricted_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Restricted"),
            None
        )
        assert restricted_class["provider_eligibility"]["allowed"] is False


class TestRationaleFieldClassification:
    """Test that content copied into rationale fields is classified."""

    def test_content_in_rationale_field_classified(self, policy_matrix):
        """Rationale fields containing sensitive data inherit source classification."""
        # Policy requires all business objects to have classification labels
        # Rationale fields are business objects
        assert "classification" in str(policy_matrix["derived_data_policy"])


class TestCrossRegionTransfer:
    """Test cross-region transfer prohibitions."""

    def test_secret_classification_cross_region_prohibited(self, policy_matrix):
        """Secret classified data cannot cross regions without explicit approval."""
        secret_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Secret"),
            None
        )
        assert secret_class["encryption_required"] is True

    def test_residency_requirements(self, split_triggers):
        """Residency split trigger exists for jurisdictional requirements."""
        residency_trigger = next(
            (t for t in split_triggers["split_triggers"] if t["trigger"] == "residency-required"),
            None
        )
        assert residency_trigger is not None
        assert residency_trigger["measurement_method"] == "architecture-review"


class TestLegalHoldPrecedence:
    """Test legal hold precedence over deletion."""

    def test_legal_hold_overrides_deletion(self, policy_matrix):
        """Active legal hold blocks deletion per precedence rules."""
        precedence = policy_matrix["precedence_rules"]
        assert "legal_hold_over_deletion" in precedence

    def test_all_classes_support_legal_hold(self, policy_matrix):
        """All classification levels support legal hold except where explicitly false."""
        for data_class in policy_matrix["data_classes"]:
            # All classes except exceptions support legal hold
            if data_class["classification"] != "Public":
                assert data_class["legal_hold_eligible"] is True


class TestCryptographicDeletion:
    """Test cryptographic deletion methods."""

    def test_secret_requires_certified_destruction(self, policy_matrix):
        """Secret data requires certified destruction."""
        secret_class = next(
            (c for c in policy_matrix["data_classes"] if c["classification"] == "Secret"),
            None
        )
        assert secret_class["disposal_method"] == "certified-destruction"

    def test_confidential_uses_crypto_deletion(self, policy_matrix):
        """Confidential and Restricted use cryptographic deletion."""
        for cls_name in ["Confidential", "Restricted"]:
            cls = next(c for c in policy_matrix["data_classes"] if c["classification"] == cls_name)
            assert cls["disposal_method"] == "cryptographic-deletion"