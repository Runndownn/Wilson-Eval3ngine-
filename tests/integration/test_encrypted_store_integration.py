"""
Integration tests for encrypted object storage (SEC-006).

Tests encryption at rest, retention policies, and KMS integration.
"""

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


class TestLocalKMSClient:
    """Tests for local KMS client (development mode)."""

    def test_kms_client_requires_master_key(self) -> None:
        """KMS client requires a master key."""
        # Clear env var for this test
        old_key = os.environ.pop("WE3_KMS_MASTER_KEY", None)
        try:
            with pytest.raises(KeyManagementError, match="Master key must be at least 32 bytes"):
                LocalKMSClient()
        finally:
            if old_key:
                os.environ["WE3_KMS_MASTER_KEY"] = old_key

    def test_kms_client_encrypt_decrypt(self) -> None:
        """KMS client can encrypt and decrypt data."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        plaintext = b"secret data"

        encrypted = kms.encrypt("test-key", plaintext)
        decrypted = kms.decrypt("test-key", encrypted)

        assert decrypted == plaintext

    def test_kms_client_generate_data_key(self) -> None:
        """KMS client can generate data encryption keys."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        dek, encrypted_dek = kms.generate_data_key("test-key")

        assert len(dek) == 32  # 256-bit key
        assert len(encrypted_dek) > 0

        # Verify we can decrypt the DEK
        decrypted_dek = kms.decrypt("test-key", encrypted_dek)
        assert decrypted_dek == dek

    def test_kms_client_key_isolation(self) -> None:
        """Different key IDs produce different encryption."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        plaintext = b"secret data"

        encrypted_a = kms.encrypt("key-a", plaintext)
        encrypted_b = kms.encrypt("key-b", plaintext)

        # Different keys should produce different ciphertext
        assert encrypted_a != encrypted_b

        # Each can only be decrypted with the correct key
        assert kms.decrypt("key-a", encrypted_a) == plaintext
        with pytest.raises(Exception):
            kms.decrypt("key-b", encrypted_a)


class TestRetentionPolicy:
    """Tests for retention policy management."""

    def test_default_policies(self) -> None:
        """Default retention policies are correctly configured."""
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

    def test_unknown_classification_defaults_to_confidential(self) -> None:
        """Unknown classifications default to confidential."""
        policy = RetentionPolicy.default("unknown")
        assert policy.classification == "confidential"


class TestEncryptedObjectStore:
    """Tests for encrypted object store operations."""

    def test_store_and_retrieve_encrypted_artifact(self, tmp_path) -> None:
        """Artifacts are encrypted at rest and can be decrypted."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "encrypted-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"sensitive evaluation data"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
            media_type="application/json",
        )

        # Verify ref properties
        assert ref.project_id == "proj_test"
        assert ref.size_bytes == len(payload)
        assert ref.encryption_key_id == "test-key-id"
        assert ref.encrypted_dek != ""
        assert ref.iv != ""
        assert ref.auth_tag != ""
        assert ref.legal_hold is False

        # Verify content is encrypted on disk
        stored_file = tmp_path / "encrypted-store" / "proj_test" / "sha256" / ref.sha256[:2] / ref.sha256
        stored_content = stored_file.read_bytes()
        assert stored_content != payload  # Must be encrypted
        assert len(stored_content) > len(payload)  # Encrypted + auth tag

        # Retrieve and verify decryption
        decrypted = store.get_bytes(ref)
        assert decrypted == payload

    def test_artifact_content_addressed_by_hash(self, tmp_path) -> None:
        """Artifacts are content-addressed by SHA-256."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "hash-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        payload = b"test content"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
        )

        # SHA-256 of the plaintext should match
        from wilson_eval3ngine.util import sha256_hex
        expected_hash = sha256_hex(payload)
        assert ref.sha256 == expected_hash

    def test_idempotent_write(self, tmp_path) -> None:
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

        # Same content should produce same hash
        assert ref1.sha256 == ref2.sha256

    def test_project_isolation(self, tmp_path) -> None:
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

    def test_retention_policy_enforced(self, tmp_path) -> None:
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

    def test_verify_integrity(self, tmp_path) -> None:
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

    def test_verify_detects_corruption(self, tmp_path) -> None:
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

    def test_metadata_sidecar_created(self, tmp_path) -> None:
        """Metadata sidecar is created with encryption info."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "metadata-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        ref = store.put_bytes(
            project_id="proj_test",
            payload=b"test data",
            metadata={"source": "test"},
        )

        metadata_file = tmp_path / "metadata-store" / "proj_test" / "sha256" / ref.sha256[:2] / f"{ref.sha256}.encrypted.json"
        assert metadata_file.exists()

        with metadata_file.open() as f:
            data = json.load(f)

        assert data["artifact"]["sha256"] == ref.sha256
        assert data["artifact"]["encryption_key_id"] == "test-key-id"
        assert data["metadata"]["source"] == "test"

    def test_retention_compliance_check(self, tmp_path) -> None:
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


class TestEncryptedStoreSecurity:
    """Security tests for encrypted object store."""

    def test_encryption_at_rest(self, tmp_path) -> None:
        """Content is encrypted at rest, not plaintext."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "security-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        plaintext = b"this should not be visible on disk"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=plaintext,
        )

        # Read raw file content
        stored_file = tmp_path / "security-store" / "proj_test" / "sha256" / ref.sha256[:2] / ref.sha256
        raw_content = stored_file.read_bytes()

        # Plaintext must not be visible in stored content
        assert plaintext not in raw_content

    def test_different_keys_produce_different_ciphertext(self, tmp_path) -> None:
        """Same plaintext with different KMS keys produces different ciphertext."""
        kms = LocalKMSClient(master_key=b"0" * 32)

        store_a = EncryptedObjectStore(
            root=tmp_path / "key-a-store",
            kms_client=kms,
            kms_key_id="key-a",
        )
        store_b = EncryptedObjectStore(
            root=tmp_path / "key-b-store",
            kms_client=kms,
            kms_key_id="key-b",
        )

        plaintext = b"same plaintext"
        ref_a = store_a.put_bytes(
            project_id="proj_test",
            payload=plaintext,
        )
        ref_b = store_b.put_bytes(
            project_id="proj_test",
            payload=plaintext,
        )

        # Same hash (content-addressed)
        assert ref_a.sha256 == ref_b.sha256

        # Different encryption
        assert ref_a.encrypted_dek != ref_b.encrypted_dek
        assert ref_a.iv != ref_b.iv

        # File contents should differ
        file_a = tmp_path / "key-a-store" / "proj_test" / "sha256" / ref_a.sha256[:2] / ref_a.sha256
        file_b = tmp_path / "key-b-store" / "proj_test" / "sha256" / ref_b.sha256[:2] / ref_b.sha256

        assert file_a.read_bytes() != file_b.read_bytes()

    def test_invalid_project_id_rejected(self, tmp_path) -> None:
        """Invalid project IDs are rejected."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "validation-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        with pytest.raises(ValueError, match="invalid project_id"):
            store.put_bytes(
                project_id="../etc/passwd",  # Path traversal attempt
                payload=b"data",
            )

    def test_large_payload_rejected(self, tmp_path) -> None:
        """Payloads exceeding maximum size are rejected."""
        kms = LocalKMSClient(master_key=b"0" * 32)
        store = EncryptedObjectStore(
            root=tmp_path / "size-store",
            kms_client=kms,
            kms_key_id="test-key-id",
        )

        large_payload = b"x" * (101 * 1024 * 1024)  # 101MB

        with pytest.raises(ValueError, match="payload exceeds maximum size"):
            store.put_bytes(
                project_id="proj_test",
                payload=large_payload,
            )
