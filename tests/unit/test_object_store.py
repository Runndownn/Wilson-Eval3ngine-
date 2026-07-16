"""Tests for content-addressed object storage.

T3.1.3 - Immutable content-addressed object storage.
"""

from __future__ import annotations


import pytest

from wilson_eval3ngine.evidence.store import (
    ArtifactRef,
    LocalArtifactStore,
)
from wilson_eval3ngine.storage.object_store import (
    SCOPED_PATH_PATTERN,
    S3ObjectStore,
)


class TestArtifactRef:
    """Test suite for artifact reference."""

    def test_artifact_ref_has_required_fields(self):
        """Artifact ref contains all required fields."""
        ref = ArtifactRef(
            project_id="proj_test",
            sha256="a" * 64,
            media_type="application/json",
            size_bytes=1024,
            relative_path="objects/proj_test/sha256/aa/aaaa",
            created_at="2026-01-01T00:00:00Z",
        )
        assert ref.project_id == "proj_test"
        assert ref.size_bytes == 1024


class TestLocalArtifactStore:
    """Test suite for local content-addressed artifact store."""

    def test_put_bytes_creates_content_addressed_path(self, tmp_path):
        """put_bytes creates path based on content hash."""
        store = LocalArtifactStore(tmp_path)
        payload = b"test content"
        ref = store.put_bytes(
            project_id="proj_test",
            payload=payload,
            media_type="application/octet-stream",
        )
        # SHA256 is deterministic
        assert len(ref.sha256) == 64
        assert ref.size_bytes == len(payload)

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts are blocked in get_bytes."""
        store = LocalArtifactStore(tmp_path / "safe_root")

        ref = ArtifactRef(
            project_id="proj_test",
            sha256="a" * 64,
            media_type="application/octet-stream",
            size_bytes=1024,
            relative_path="../../../etc/passwd",
            created_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(ValueError, match="escaped"):
            store.get_bytes(ref)


class TestScopedPathPattern:
    """Test suite for scoped path pattern."""

    def test_scoped_path_pattern_exists(self):
        """Scoped path pattern constant is defined."""
        assert "project_id" in SCOPED_PATH_PATTERN
        assert "classification" in SCOPED_PATH_PATTERN
        assert "sha256" in SCOPED_PATH_PATTERN


class TestS3ObjectStoreValidation:
    """Test suite for S3ObjectStore validation."""

    def test_invalid_classification_rejected(self):
        """Invalid classifications are rejected."""
        store = S3ObjectStore(bucket="test-bucket")
        with pytest.raises(ValueError, match="invalid classification"):
            store._validate_classification("invalid_level")

    def test_valid_classifications_accepted(self):
        """Valid classifications are normalized."""
        store = S3ObjectStore(bucket="test-bucket")
        assert store._validate_classification("PUBLIC") == "public"
        assert store._validate_classification("Internal") == "internal"
        assert store._validate_classification("CONFIDENTIAL") == "confidential"
        assert store._validate_classification("restricted") == "restricted"

    def test_invalid_mime_type_rejected(self):
        """Invalid MIME types are rejected."""
        store = S3ObjectStore(bucket="test-bucket")
        with pytest.raises(ValueError, match="invalid media_type"):
            store._validate_mime_type("invalid", b"test")

    def test_payload_size_limit_enforced(self):
        """Payload size limit is enforced."""
        store = S3ObjectStore(bucket="test-bucket")
        large_payload = b"x" * (101 * 1024 * 1024)  # 101MB
        with pytest.raises(ValueError, match="payload exceeds maximum size"):
            store.put("proj", "public", large_payload, "application/octet-stream")


class TestS3ObjectStoreKeys:
    """Test suite for S3ObjectStore key generation."""

    def test_scoped_key_generation(self):
        """Scoped key includes all required components."""
        store = S3ObjectStore(bucket="test-bucket", kms_key_id="key-123")
        key = store._scoped_key("proj_123", "confidential", "abcdef123456")
        assert "proj_123" in key
        assert "confidential" in key
        assert "sha256" in key
        assert "abcdef" in key

    def test_staging_key_prefix(self):
        """Staging keys have staging prefix."""
        store = S3ObjectStore(bucket="test-bucket")
        staging = store._scoped_key("proj_123", "internal", "abcdef", staging=True)
        final = store._scoped_key("proj_123", "internal", "abcdef", staging=False)
        assert store.STAGING_PREFIX in staging
        assert store.STAGING_PREFIX not in final
        assert staging.replace(store.STAGING_PREFIX, "") == final