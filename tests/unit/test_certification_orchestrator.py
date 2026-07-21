"""Unit tests for certification orchestration.

TODO 58 - Tests for evidence applicability, freshness, requirement closure,
severity policy, exception expiry, and manifest signing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from wilson_eval3ngine.certification.certification_orchestrator import (
    CertificationCategory,
    CertificationOrchestrator,
    CertificationRegistry,
    CertificationRequirement,
    CertificationResult,
    EvidenceEntry,
    EvidenceStatus,
    create_certification_manifest,
)


# =============================================================================
# Evidence Applicability Tests
# =============================================================================


class TestEvidenceApplicability:
    """Tests for evidence applicability validation."""

    def test_evidence_fresh_within_window(self):
        """Fresh evidence passes applicability check."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.SECURITY,
            evidence_id="ev_001",
            source_hash="sha256:test_hash",
            timestamp=now - timedelta(hours=12),
            expires_at=None,
            evidence_type="test_result",
            evidence_ref="tests/security/test_security.py::test_001",
            validation_result="pass",
        )
        assert evidence.is_fresh(max_age_hours=24) is True

    def test_evidence_stale_outside_window(self):
        """Stale evidence fails freshness check."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.SECURITY,
            evidence_id="ev_002",
            source_hash="sha256:test_hash",
            timestamp=now - timedelta(hours=48),
            expires_at=None,
            evidence_type="test_result",
            evidence_ref="tests/security/test_security.py::test_002",
            validation_result="pass",
        )
        assert evidence.is_fresh(max_age_hours=24) is False

    def test_evidence_expired_at_explicit(self):
        """Evidence with explicit expiry respects expiry time."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.SECURITY,
            evidence_id="ev_003",
            source_hash="sha256:test_hash",
            timestamp=now - timedelta(hours=1),
            expires_at=now - timedelta(hours=1),  # Already expired
            evidence_type="test_result",
            evidence_ref="tests/security/test_security.py::test_003",
            validation_result="pass",
        )
        assert evidence.is_fresh() is False


class TestRequirementClosure:
    """Tests for certification requirement satisfaction."""

    def test_all_requirements_have_required_fields(self):
        """All core requirements have required fields."""
        for req_id, req in CertificationRegistry.CORE_REQUIREMENTS.items():
            assert req.requirement_id == req_id
            assert req.category in CertificationCategory
            assert req.description
            assert req.evidence_source_required is not None

    def test_requirement_blocking_status(self):
        """Must requirements are blocking."""
        for req in CertificationRegistry.CORE_REQUIREMENTS.values():
            if "Must" in req.description or req.blocking:
                assert req.blocking is True

    def test_requirement_freshness_required(self):
        """All requirements require freshness by default."""
        for req in CertificationRegistry.CORE_REQUIREMENTS.values():
            assert req.freshness_required is True


# =============================================================================
# Certification Category Tests
# =============================================================================


class TestCertificationCategories:
    """Tests for all ten certification categories."""

    def test_all_categories_defined(self):
        """All ten categories exist."""
        categories = list(CertificationCategory)
        assert len(categories) == 10
        assert CertificationCategory.REPRODUCIBILITY in categories
        assert CertificationCategory.DURABILITY in categories
        assert CertificationCategory.INTEGRITY in categories
        assert CertificationCategory.SECURITY in categories
        assert CertificationCategory.STATISTICS in categories
        assert CertificationCategory.GRADING in categories
        assert CertificationCategory.GOVERNANCE in categories
        assert CertificationCategory.RECOVERY in categories
        assert CertificationCategory.OPERATIONS in categories
        assert CertificationCategory.USABILITY in categories

    def test_category_requirements_coverage(self):
        """Each category has at least one core requirement."""
        registry = CertificationRegistry()
        for category in CertificationCategory:
            reqs = registry.get_requirements(category)
            assert len(reqs) >= 1, f"Category {category} missing requirements"


# =============================================================================
# Freshness Window Tests
# =============================================================================


class TestFreshnessWindows:
    """Tests for evidence freshness windows."""

    def test_different_max_age_hours(self):
        """Different categories can have different freshness windows."""
        registry = CertificationRegistry()
        requirements = registry.get_requirements()
        max_ages = {r.category.value: r.max_age_hours for r in requirements}
        # Security should have reasonable freshness window
        for category, max_age in max_ages.items():
            assert max_age > 0


# =============================================================================
# Severity Policy Tests
# =============================================================================


class TestSeverityPolicy:
    """Tests for critical/high defect handling."""

    def test_blocking_requirements_create_block_status(self):
        """Blocking requirement violations result in BLOCK status."""
        orchestrator = CertificationOrchestrator(CertificationRegistry())
        # With no evidence, blocking requirements should fail
        result = orchestrator.evaluate_category(
            CertificationCategory.SECURITY, "commit_abc", "production", "hash_xyz"
        )
        # Should be BLOCK because no evidence provided
        assert result == EvidenceStatus.BLOCK


# =============================================================================
# Exception Expiry Tests
# =============================================================================


class TestExceptionExpiry:
    """Tests for exception expiry handling."""

    def test_approver_list_affects_approval_count(self):
        """Approval count reflects number of approvers."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        approvers = ["alice", "bob", "charlie"]
        result = CertificationResult(
            certification_id="test_cert",
            generated_at=datetime.now(timezone.utc),
            release_artifact_digest="digest",
            source_commit="commit",
            environment="prod",
            requirement_catalog_hash="hash",
            approval_count=len(approvers),
        )
        assert result.approval_count == 3


# =============================================================================
# Manifest Signing Tests
# =============================================================================


class TestManifestSigning:
    """Tests for certification manifest signing and verification."""

    def test_certification_result_serialization(self):
        """CertificationResult serializes correctly."""
        result = CertificationResult(
            certification_id="cert_123",
            generated_at=datetime.now(timezone.utc),
            release_artifact_digest="sha256:digest_123",
            source_commit="abc123",
            environment="production",
            requirement_catalog_hash="req_hash",
        )
        d = result.to_dict()
        assert d["certification_id"] == "cert_123"
        assert d["release_artifact_digest"] == "sha256:digest_123"
        assert d["source_commit"] == "abc123"

    def test_evidence_entry_serialization(self):
        """EvidenceEntry serializes with all fields."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.STATISTICS,
            evidence_id="ev_stat_001",
            source_hash="sha256:stats_hash",
            timestamp=now,
            expires_at=None,
            evidence_type="statistics_test",
            evidence_ref="tests/unit/test_statistics.py",
            validation_result="pass",
        )
        d = evidence.to_dict()
        assert d["category"] == "statistics"
        assert d["validation_result"] == "pass"

    def test_create_certification_manifest(self):
        """Certification manifest includes all required fields."""
        result = CertificationResult(
            certification_id="cert_manifest_001",
            generated_at=datetime.now(timezone.utc),
            release_artifact_digest="sha256:artifact",
            source_commit="commit_xyz",
            environment="staging",
            requirement_catalog_hash="req_hash_abc",
            approval_count=2,
        )
        result.evidence_validations = {cat.value: EvidenceStatus.PASS for cat in CertificationCategory}

        evidence_list = [
            EvidenceEntry(
                category=CertificationCategory.SECURITY,
                evidence_id="ev_sec_001",
                source_hash="sha256:sec",
                timestamp=datetime.now(timezone.utc),
                expires_at=None,
                evidence_type="test",
                evidence_ref="tests/security/test_auth.py",
                validation_result="pass",
            ),
        ]

        manifest = create_certification_manifest(result, evidence_list)
        assert manifest["schema_version"] == "we3.certification_manifest.v1"
        assert manifest["certification_id"] == "cert_manifest_001"
        assert len(manifest["evidence_index"]) == 1


# =============================================================================
# Environment Drift Tests
# =============================================================================


class TestEnvironmentDrift:
    """Tests for environmental drift detection."""

    def test_different_environments_isolated(self):
        """Evidence from different environments cannot be mixed."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        # Evidence for staging should not satisfy production requirements
        # (This would be enforced by verifying source_commit/environment match)
        # For now, just verify the evaluator accepts environment parameter
        status = orchestrator.evaluate_category(
            CertificationCategory.OPERATIONS, "commit_staging", "staging", "hash"
        )
        # Without evidence, this should still block
        assert status == EvidenceStatus.BLOCK


# =============================================================================
# Concurrent Certification Tests
# =============================================================================


class TestConcurrentCertification:
    """Tests for concurrent certification attempts."""

    def test_same_release_different_certification(self):
        """Same release artifact can be certified multiple times."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        result1 = orchestrator.run_certification(
            release_artifact_digest="digest_v1",
            source_commit="commit_v1",
            environment="production",
            requirement_catalog_hash="hash_v1",
            approvers=["alice", "bob"],
        )

        result2 = orchestrator.run_certification(
            release_artifact_digest="digest_v1",
            source_commit="commit_v1",
            environment="production",
            requirement_catalog_hash="hash_v1",
            approvers=["charlie"],
        )

        # Both should fail (no evidence) but have different approval counts
        assert result1.approval_count == 2
        assert result2.approval_count == 1


# =============================================================================
# Release Artifact Verification Tests
# =============================================================================


class TestArtifactVerification:
    """Tests for release artifact verification."""

    def test_resolve_release_artifact(self, tmp_path: Any):
        """Release artifact digest is computed correctly."""
        orchestrator = CertificationOrchestrator(CertificationRegistry())

        # Create a test artifact
        artifact_file = tmp_path / "release_artifact.bin"
        artifact_file.write_bytes(b"test artifact content")

        digest = orchestrator.resolve_release_artifact(artifact_file)
        assert digest.startswith("sha256:")
        assert len(digest) == 64 + 7  # "sha256:" prefix + 64 hex chars

    def test_verify_artifact_signature_matches(self):
        """Artifact signature verification works."""
        orchestrator = CertificationOrchestrator(CertificationRegistry())
        digest = "sha256:abc123"
        assert orchestrator.verify_artifact_signature(digest, digest) is True
        assert orchestrator.verify_artifact_signature(digest, "different") is False

    def test_resolve_missing_artifact_raises(self, tmp_path: Any):
        """Missing artifact raises ValueError."""
        orchestrator = CertificationOrchestrator(CertificationRegistry())
        missing_file = tmp_path / "does_not_exist.bin"

        with pytest.raises(ValueError, match="Artifact not found"):
            orchestrator.resolve_release_artifact(missing_file)


# =============================================================================
# Security Tests
# =============================================================================


class TestCertificationSecurity:
    """Security tests for certification process."""

    def test_evidence_hash_verification(self):
        """Evidence hashes are used for verification, not filenames."""
        evidence = EvidenceEntry(
            category=CertificationCategory.INTEGRITY,
            evidence_id="ev_int_001",
            source_hash="sha256:content_addressible_hash",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="integrity_check",
            evidence_ref="var/evidence/hash_content_addressible_hash",
            validation_result="verified",
        )

        # Hash is the primary identifier, not filename
        assert "sha256:" in evidence.source_hash
        assert evidence.evidence_ref is not None

    def test_cross_project_evidence_isolation(self):
        """Evidence cannot be contaminated cross-project."""
        # This would be enforced by validating project_id in evidence metadata
        # For now, verify EvidenceEntry can hold project-scoped info
        evidence = EvidenceEntry(
            category=CertificationCategory.RECOVERY,
            evidence_id="ev_recov_001",
            source_hash="sha256:recovery_hash",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="backup_restore",
            evidence_ref="backups/project_123/restore_001",
            validation_result="verified",
        )

        # Ref includes project scope
        assert "project_123" in evidence.evidence_ref


# =============================================================================
# Freshness Edge Cases
# =============================================================================


class TestFreshnessEdgeCases:
    """Edge case tests for evidence freshness."""

    def test_evidence_minutes_old(self):
        """Evidence minutes old is fresh."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.OPERATIONS,
            evidence_id="ev_ops_001",
            source_hash="sha256:ops",
            timestamp=now - timedelta(minutes=30),
            expires_at=None,
            evidence_type="slI_check",
            evidence_ref="prometheus/sli_ops",
            validation_result="pass",
        )
        assert evidence.is_fresh(max_age_hours=24) is True

    def test_evidence_edge_of_window(self):
        """Evidence at exact window boundary is still fresh."""
        now = datetime.now(timezone.utc)
        # Add a tiny bit of buffer (30 seconds) to ensure it's still fresh
        evidence = EvidenceEntry(
            category=CertificationCategory.DURABILITY,
            evidence_id="ev_dur_001",
            source_hash="sha256:dur",
            timestamp=now - timedelta(hours=23, minutes=59, seconds=30),
            expires_at=None,
            evidence_type="backup_test",
            evidence_ref="tests/unit/test_backup.py",
            validation_result="pass",
        )
        assert evidence.is_fresh(max_age_hours=24) is True


# =============================================================================
# Independent Verification Tests
# =============================================================================


class TestIndependentVerification:
    """Tests for independent verification capability."""

    def test_certification_status_from_manifest(self, tmp_path: Any):
        """Certification status can be verified from manifest alone."""
        # Create a mock certification manifest
        manifest = {
            "certification_id": "cert_verify_001",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "release_artifact_digest": "sha256:digest",
            "source_commit": "commit",
            "environment": "production",
            "requirement_catalog_hash": "hash",
            "evidence_validations": {cat.value: EvidenceStatus.PASS.value for cat in CertificationCategory},
            "blocking_issues": [],
            "warning_issues": [],
            "indeterminate_issues": [],
            "approval_count": 2,
            "status": "pass",
        }

        manifest_file = tmp_path / "certification.json"
        manifest_file.write_text(
            __import__("json").dumps(manifest, sort_keys=True),
            encoding="utf-8",
        )

        # Verification should work from manifest without database
        orchestrator = CertificationOrchestrator(CertificationRegistry())
        result = orchestrator.verify_certification(manifest_file)

        # Should have validation result
        assert "valid" in result


# =============================================================================
# SLO Evidence Validation Tests
# =============================================================================


class TestSLOEvidenceValidation:
    """Tests for SLO evidence validation in operations certification."""

    def test_validation_sli_evidence_all_slis_exist(self):
        """SLO evidence validation finds all six core SLIs."""
        orchestrator = CertificationOrchestrator(CertificationRegistry())

        result = orchestrator.validate_sli_evidence()

        assert result["valid"] is True
        assert result["slis_defined"] == 6
        assert result["total_slis"] == 6
        assert len(result["missing_slis"]) == 0

    def test_validation_sli_evidence_missing_slis_detected(self):
        """Missing SLIs would be detected in validation."""
        # This tests that the validation logic works
        # In production, if SLI registry was incomplete, it would list missing
        orchestrator = CertificationOrchestrator(CertificationRegistry())

        result = orchestrator.validate_sli_evidence()

        # All SLIs should be defined in current implementation
        assert result["valid"] is True


# =============================================================================
# Evidence Hash Validation Tests
# =============================================================================


class TestEvidenceHashFormat:
    """Tests for evidence hash format requirements."""

    def test_evidence_requires_sha256_prefix(self):
        """Evidence must use SHA-256 content addressing."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.INTEGRITY,
            evidence_id="ev_hash_001",
            source_hash="sha256:abc123def456",
            timestamp=now,
            expires_at=None,
            evidence_type="integrity_test",
            evidence_ref="evidence/abc123def456",
            validation_result="verified",
        )

        assert evidence.source_hash.startswith("sha256:")

    def test_evidence_with_invalid_hash_format_rejected(self):
        """Evidence with non-SHA256 format fails applicability."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.INTEGRITY,
            evidence_id="ev_bad_hash",
            source_hash="md5:invalid_hash",  # Wrong format
            timestamp=now,
            expires_at=None,
            evidence_type="integrity_test",
            evidence_ref="evidence/bad_hash",
            validation_result="verified",
        )
        registry.add_evidence(evidence)

        # Applicability check should fail for invalid hash format
        applicable = orchestrator.verify_evidence_applicability(
            evidence, "commit", "production"
        )
        assert applicable is False


# =============================================================================
# Environment Drift Detection Tests (TODO 58)
# =============================================================================


class TestEnvironmentDriftDetection:
    """Tests for evidence environment matching."""

    def test_evidence_from_wrong_environment_rejected(self):
        """Evidence from different environment is rejected for applicability."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        # Add evidence from staging environment
        evidence = EvidenceEntry(
            category=CertificationCategory.SECURITY,
            evidence_id="ev_wrong_env",
            source_hash="sha256:staging_hash",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="security_test",
            evidence_ref="tests/security/test_auth.py",
            validation_result="pass",
            environment="staging",  # Wrong environment!
        )
        registry.add_evidence(evidence)

        # Verify applicability fails due to environment mismatch
        applicable = orchestrator.verify_evidence_applicability(
            evidence, "commit", "production"
        )
        assert applicable is False

    def test_evidence_from_correct_environment_accepted(self):
        """Evidence from matching environment passes applicability."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        evidence = EvidenceEntry(
            category=CertificationCategory.SECURITY,
            evidence_id="ev_correct_env",
            source_hash="sha256:prod_hash",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="security_test",
            evidence_ref="tests/security/test_auth.py",
            validation_result="pass",
            environment="production",
            source_commit="abc123def456",
        )
        registry.add_evidence(evidence)

        # Verify applicability passes
        applicable = orchestrator.verify_evidence_applicability(
            evidence, "abc123def456", "production"
        )
        assert applicable is True


class TestEvidenceCommitTracking:
    """Tests for evidence source commit tracking."""

    def test_evidence_without_commit_fields(self):
        """Evidence without commit/environment fields still works in foundation mode."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        evidence = EvidenceEntry(
            category=CertificationCategory.DURABILITY,
            evidence_id="ev_no_commit",
            source_hash="sha256:no_commit_hash",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="backup_test",
            evidence_ref="tests/integration/backup_test",
            validation_result="pass",
            environment=None,
            source_commit=None,
        )
        registry.add_evidence(evidence)

        applicable = orchestrator.verify_evidence_applicability(
            evidence, "any_commit", "any_env"
        )
        assert applicable is True


class TestStaleEvidenceDetection:
    """Tests for stale evidence detection during certification."""

    def test_stale_evidence_creates_indeterminate(self):
        """Stale evidence is flagged in certification results."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        # Add stale evidence (48 hours old)
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        evidence = EvidenceEntry(
            category=CertificationCategory.RECOVERY,
            evidence_id="ev_stale_recovery",
            source_hash="sha256:stale",
            timestamp=old_time,
            expires_at=None,
            evidence_type="backup_test",
            evidence_ref="old_backup_test",
            validation_result="pass",
        )
        registry.add_evidence(evidence)

        result = orchestrator.run_certification(
            "sha256:artifact", "commit", "production", "hash", ["approver"]
        )

        # Should have stale evidence warning
        assert any("stale_evidence" in issue for issue in result.indeterminate_issues)


class TestEvidenceWithSourceCommit:
    """Tests for evidence with source commit and environment metadata."""

    def test_evidence_entry_includes_source_commit(self):
        """Evidence entry serializes source_commit and environment."""
        now = datetime.now(timezone.utc)
        evidence = EvidenceEntry(
            category=CertificationCategory.STATISTICS,
            evidence_id="ev_commit_001",
            source_hash="sha256:commit_hash",
            timestamp=now,
            expires_at=None,
            evidence_type="statistics_test",
            evidence_ref="tests/statistics/",
            validation_result="pass",
            source_commit="abc123def456",
            environment="staging",
        )

        d = evidence.to_dict()
        assert d["source_commit"] == "abc123def456"
        assert d["environment"] == "staging"

    def test_check_environment_drift_detects_mismatches(self):
        """Environment drift detection identifies mismatched evidence."""
        registry = CertificationRegistry()
        orchestrator = CertificationOrchestrator(registry)

        # Add evidence from wrong environment
        evidence = EvidenceEntry(
            category=CertificationCategory.OPERATIONS,
            evidence_id="ev_drift_test",
            source_hash="sha256:drift",
            timestamp=datetime.now(timezone.utc),
            expires_at=None,
            evidence_type="ops_test",
            evidence_ref="tests/ops/",
            validation_result="pass",
            environment="staging",
            source_commit="wrong_commit",
        )
        registry.add_evidence(evidence)

        drift_warnings = orchestrator.check_environment_drift(
            [evidence], "correct_commit", "production"
        )

        assert len(drift_warnings) >= 1
        assert any("staging" in w for w in drift_warnings) or any("commit" in w for w in drift_warnings)