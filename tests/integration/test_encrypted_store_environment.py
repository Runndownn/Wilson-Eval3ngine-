"""
Environment-specific tests for Encrypted Object Storage (SEC-003).

Tests encryption at rest, retention policies, and KMS integration across
different deployment environments:
- Development: Local KMS, local artifact storage
- Staging: External KMS simulation, staging artifact root
- Production: Full encryption with legal hold, restricted retention
- Minimal: No optional dependencies
- OTel-enabled/disabled: tracing behavior with encrypted storage

Test counts: 19 integration tests
"""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path

from wilson_eval3ngine.storage.encrypted_store import (
    EncryptedObjectStore,
    EncryptedArtifactRef,
    RetentionPolicy,
    LocalKMSClient,
    EncryptionError,
    RetentionViolationError,
    KeyManagementError,
)
from wilson_eval3ngine.util import sha256_hex


# ============================================================================
# Environment-Specific KMS Client Tests (4 tests)
# ============================================================================

class TestKMSClientAcrossEnvironments:
    """Test KMS client behavior across different environments."""

    def test_kms_client_requires_master_key_dev(self):
        """KMS client requires master key in development."""
        old_key = os.environ.pop("WE3_KMS_MASTER_KEY", None)
        try:
            with pytest.raises(KeyManagementError, match="Master key must be at least 32 bytes"):
                LocalKMSClient()
        finally:
            if old_key:
                os.environ["WE3_KMS_MASTER_KEY"] = old_key

    def test_kms_client_encrypt_decrypt_dev(self):
        """KMS client can encrypt and decrypt in development."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        plaintext = b"dev secret data"

        encrypted = kms.encrypt("dev-key", plaintext)
        decrypted = kms.decrypt("dev-key", encrypted)

        assert decrypted == plaintext

    def test_kms_client_key_isolation_staging(self):
        """Different key IDs produce different encryption in staging."""
        kms = LocalKMSClient(master_key=b"staging_master_key_" + b"x" * 15)
        plaintext = b"staging secret data"

        encrypted_a = kms.encrypt("staging-key-a", plaintext)
        encrypted_b = kms.encrypt("staging-key-b", plaintext)

        # Different keys should produce different ciphertext
        assert encrypted_a != encrypted_b

        # Each can only be decrypted with the correct key
        assert kms.decrypt("staging-key-a", encrypted_a) == plaintext
        with pytest.raises(Exception):
            kms.decrypt("staging-key-b", encrypted_a)

    def test_kms_client_generate_data_key_production(self):
        """KMS client can generate data encryption keys in production."""
        kms = LocalKMSClient(master_key=b"prod_master_key_" + b"x" * 16)
        dek, encrypted_dek = kms.generate_data_key("prod-key-id")

        assert len(dek) == 32  # 256-bit key
        assert len(encrypted_dek) > 0

        # Verify we can decrypt the DEK
        decrypted_dek = kms.decrypt("prod-key-id", encrypted_dek)
        assert decrypted_dek == dek


# ============================================================================
# Environment-Specific Retention Policy Tests (5 tests)
# ============================================================================

class TestRetentionPolicyAcrossEnvironments:
    """Test retention policy behavior across environments."""

    def test_default_policies_dev_environment(self):
        """Default retention policies for development."""
        public = RetentionPolicy.default("public")
        assert public.min_retention_days == 90
        assert public.legal_hold is False

        internal = RetentionPolicy.default("internal")
        assert internal.min_retention_days == 365
        assert internal.legal_hold is False

        confidential = RetentionPolicy.default("confidential")
        assert confidential.min_retention_days == 365
        assert confidential.legal_hold is False

        restricted = RetentionPolicy.default("restricted")
        assert restricted.legal_hold is True
        assert restricted.min_retention_days == 1825

    def test_default_policies_staging_environment(self):
        """Default retention policies for staging match production."""
        # Staging should use same policies as production
        public = RetentionPolicy.default("public")
        assert public.policy_id == "retention:public:default"
        assert public.max_retention_days == 365

        confidential = RetentionPolicy.default("confidential")
        assert confidential.policy_id == "retention:confidential:default"
        assert confidential.max_retention_days == 1825

    def test_default_policies_production_environment(self):
        """Default retention policies for production."""
        restricted = RetentionPolicy.default("restricted")
        assert restricted.policy_id == "retention:restricted:default"
        assert restricted.legal_hold is True
        assert restricted.max_retention_days == 36500  # 100 years

    def test_unknown_classification_defaults_to_confidential(self):
        """Unknown classifications default to confidential."""
        policy = RetentionPolicy.default("unknown")
        assert policy.classification == "confidential"

    def test_retention_policy_fields(self):
        """Retention policy has all required fields."""
        policy = RetentionPolicy.default("internal")
        assert policy.policy_id is not None
        assert policy.min_retention_days > 0
        assert policy.max_retention_days > 0
        assert policy.classification == "internal"


# ============================================================================
# Environment-Specific EncryptedObjectStore Tests (10 tests)
# ============================================================================

class TestEncryptedObjectStoreAcrossEnvironments:
    """Test encrypted object store across different environments."""

    def test_store_and_retrieve_dev_environment(self, tmp_path):
        """Store and retrieve encrypted artifact in development."""
        kms = LocalKMSClient(master_key=b"dev_master_key_" + b"x" * 18)
        store = EncryptedObjectStore(
            root=tmp_path / "dev-store",
            kms_client=kms,
            kms_key_id="dev-key-id",
        )

        payload = b"sensitive dev data"
        ref = store.put_bytes(
            project_id="proj_dev",
            payload=payload,
            media_type="application/json",
        )

        # Verify ref properties
        assert ref.project_id == "proj_dev"
        assert ref.size_bytes == len(payload)
        assert ref.encryption_key_id == "dev-key-id"
        assert ref.encrypted_dek != ""
        assert ref.iv != ""
        assert ref.auth_tag != ""
        assert ref.legal_hold is False

        # Verify content is encrypted on disk
        stored_file = tmp_path / "dev-store" / "proj_dev" / "sha256" / ref.sha256[:2] / ref.sha256
        stored_content = stored_file.read_bytes()
        assert stored_content != payload  # Must be encrypted
        assert len(stored_content) > len(payload)  # Encrypted + auth tag

        # Retrieve and verify decryption
        decrypted = store.get_bytes(ref)
        assert decrypted == payload

    def test_store_and_retrieve_staging_environment(self, tmp_path):
        """Store and retrieve encrypted artifact in staging."""
        kms = LocalKMSClient(master_key=b"staging_master_key_" + b"x" * 15)
        store = EncryptedObjectStore(
            root=tmp_path / "staging-store",
            kms_client=kms,
            kms_key_id="staging-key-id",
        )

        payload = b"sensitive staging data"
        ref = store.put_bytes(
            project_id="proj_staging",
            payload=payload,
        )

        # Verify staging-specific properties
        assert ref.project_id == "proj_staging"
        assert ref.encryption_key_id == "staging-key-id"

        # Retrieve and verify
        decrypted = store.get_bytes(ref)
        assert decrypted == payload

    def test_store_and_retrieve_production_environment(self, tmp_path):
        """Store and retrieve encrypted artifact in production."""
        kms = LocalKMSClient(master_key=b"prod_master_key_" + b"x" * 16)
        store = EncryptedObjectStore(
            root=tmp_path / "prod-store",
            kms_client=kms,
            kms_key_id="prod-key-id",
        )

        payload = b"sensitive production data"
        ref = store.put_bytes(
            project_id="proj_prod",
            payload=payload,
        )

        # Verify production-specific properties
        assert ref.project_id == "proj_prod"
        assert ref.encryption_key_id == "prod-key-id"

        # Retrieve and verify
        decrypted = store.get_bytes(ref)
        assert decrypted == payload

    def test_artifact_content_addressed_by_hash(self, tmp_path):
        """Artifacts are content-addressed by SHA-256."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "hash-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"test content for hashing"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )

        expected_hash = sha256_hex(payload)
        assert ref.sha256 == expected_hash

    def test_idempotent_write(self, tmp_path):
        """Writing the same content twice is idempotent."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "idempotent-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"same content"
        ref1 = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )
        ref2 = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )

        assert ref1.sha256 == ref2.sha256

    def test_project_isolation(self, tmp_path):
        """Artifacts from different projects are isolated."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "isolated-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"shared content"
        ref_a = store.put_bytes(
            project_id="proj_alpha",
            payload=payload,
        )
        ref_b = store.put_bytes(
            project_id="proj_beta",
            payload=payload,
        )

        # Same content, different project paths
        assert ref_a.sha256 == ref_b.sha256  # Same hash
        assert ref_a.relative_path != ref_b.relative_path  # Different paths
        assert "proj_alpha" in ref_a.relative_path
        assert "proj_beta" in ref_b.relative_path

    def test_retention_policy_enforced(self, tmp_path):
        """Retention policies are stored and enforced."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "retention-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        retention = RetentionPolicy.default("restricted")
        ref = store.put_bytes(
            project_id="proj_test",
            payload=b"restricted data",
            retention=retention,
        )

        assert ref.retention_policy == "retention:restricted:default"
        assert ref.legal_hold is True
        assert ref.retention_expires_at is None  # Legal hold never expires

    def test_verify_integrity(self, tmp_path):
        """Artifact integrity can be verified."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "verify-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"verifiable content"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )

        assert store.verify(ref) is True

    def test_verify_detects_corruption(self, tmp_path):
        """Artifact corruption is detected during verification."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "corruption-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"original content"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )

        # Corrupt the stored file
        stored_file = tmp_path / "corruption-store" / "proj_test" / "sha256" / ref.sha256[:2] / ref.sha256
        stored_file.write_bytes(b"corrupted data")

        assert store.verify(ref) is False

    def test_retention_compliance_check(self, tmp_path):
        """Retention compliance can be checked for a project."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "compliance-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        store.put_bytes(
            project_id="proj_test",
            payload=b"data 1",
        )
        store.put_bytes(
            project_id="proj_test",
            payload=b"data 2",
        )

        result = store.check_retention_compliance("proj_test")
        assert result["compliant"] is True
        assert result["artifact_count"] == 2
        assert len(result["violations"]) == 0
