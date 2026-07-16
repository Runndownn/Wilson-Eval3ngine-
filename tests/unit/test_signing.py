"""Unit tests for signing and key management (TODO 40).

Tests key inventory, trust registry, audit checkpoints, rotation, and revocation.
"""
from __future__ import annotations

from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from wilson_eval3ngine.security.signing import (
    AuditCheckpoint,
    KeyInventory,
    KeyPurpose,
    TrustRegistry,
    create_audit_checkpoint,
    generate_private_key,
    load_private_key,
    sign_bytes,
    verify_bytes,
)
from wilson_eval3ngine.util import sha256_hex, utc_now


class TestKeyInventory:
    """Tests for key inventory management."""

    def test_register_key(self) -> None:
        """Key registration creates valid record."""
        inventory = KeyInventory()
        record = inventory.register_key(
            key_id="key_001",
            purpose=KeyPurpose.SIGNING,
            owner="release_authority",
        )
        assert record.key_id == "key_001"
        assert record.purpose == KeyPurpose.SIGNING
        assert record.owner == "release_authority"
        assert record.active is True
        assert record.is_valid() is True

    def test_get_key(self) -> None:
        """Can retrieve registered key."""
        inventory = KeyInventory()
        inventory.register_key("key_001", KeyPurpose.SIGNING, "release_authority")
        retrieved = inventory.get_key("key_001")
        assert retrieved is not None
        assert retrieved.key_id == "key_001"

    def test_get_nonexistent_key(self) -> None:
        """Nonexistent key returns None."""
        inventory = KeyInventory()
        assert inventory.get_key("nonexistent") is None

    def test_key_rotation(self) -> None:
        """Key rotation records parent relationship."""
        inventory = KeyInventory()
        inventory.register_key("key_old", KeyPurpose.SIGNING, "release_authority")
        
        new = inventory.rotate_key(
            "key_old",
            "key_new",
            KeyPurpose.SIGNING,
            "release_authority",
        )
        
        assert new.parent_key_id == "key_old"
        assert new.key_id == "key_new"
        assert inventory.get_key("key_new") is not None

    def test_revoke_key(self) -> None:
        """Key revocation marks key inactive."""
        inventory = KeyInventory()
        inventory.register_key("key_001", KeyPurpose.SIGNING, "release_authority")
        
        inventory.revoke_key("key_001")
        
        revoked = inventory.get_key("key_001")
        assert revoked is not None
        assert revoked.active is False
        assert revoked.is_valid() is False

    def test_list_active_keys(self) -> None:
        """List active keys can filter by purpose."""
        inventory = KeyInventory()
        inventory.register_key("key_sign", KeyPurpose.SIGNING, "release_authority")
        inventory.register_key("key_audit", KeyPurpose.AUDIT, "auditor")
        inventory.register_key("key_enc", KeyPurpose.ENCRYPTION, "security_team")
        
        all_keys = inventory.list_active_keys()
        assert len(all_keys) == 3
        
        signing_keys = inventory.list_active_keys(purpose=KeyPurpose.SIGNING)
        assert len(signing_keys) == 1
        assert signing_keys[0].key_id == "key_sign"

    def test_list_active_keys_excludes_expired(self) -> None:
        """Expired keys are excluded from active list."""
        inventory = KeyInventory()
        inventory.register_key(
            "key_expired",
            KeyPurpose.SIGNING,
            "release_authority",
            expires_at=utc_now() - timedelta(days=1),
        )
        
        active = inventory.list_active_keys()
        assert len(active) == 0

    def test_fips_validation_flag(self) -> None:
        """Keys can be marked as FIPS validated."""
        inventory = KeyInventory()
        record = inventory.register_key(
            "key_fips",
            KeyPurpose.SIGNING,
            "release_authority",
        )
        # For production, this would be set by KMS integration
        assert record.fips_validation is False


class TestTrustRegistry:
    """Tests for trust registry."""

    def test_trust_key(self) -> None:
        """Key fingerprint can be trusted."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"test_key_data")
        
        registry.trust_key(fingerprint)
        
        assert registry.is_trusted(fingerprint) is True

    def test_revoke_key(self) -> None:
        """Trusted key can be revoked."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"test_key_data")
        
        registry.trust_key(fingerprint)
        assert registry.is_trusted(fingerprint) is True
        
        registry.revoke_key(fingerprint)
        
        assert registry.is_trusted(fingerprint) is False

    def test_unknown_key_not_trusted(self) -> None:
        """Unknown keys are not trusted."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"unknown_key")
        
        assert registry.is_trusted(fingerprint) is False

    def test_verification_with_trusted_key(self) -> None:
        """Signature verification works with trusted key."""
        registry = TrustRegistry()
        
        # Create a key and sign something
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test_payload", key)
        
        # Trust the key
        registry.trust_key(envelope.public_key_fingerprint_sha256)
        
        # Verify should work
        assert verify_bytes(b"test_payload", envelope) is True
        assert registry.is_trusted(envelope.public_key_fingerprint_sha256) is True


class TestAuditCheckpoint:
    """Tests for audit checkpoint signing."""

    def test_create_checkpoint(self) -> None:
        """Audit checkpoint can be created."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test", key)
        
        now = utc_now()
        checkpoint = AuditCheckpoint(
            checkpoint_id="checkpoint_001",
            timestamp=now,
            event_window_start=now - timedelta(hours=1),
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"root"),
            signature=envelope,
            signer_key_id="key_001",
        )
        
        assert checkpoint.checkpoint_id == "checkpoint_001"
        assert checkpoint.event_count == 100
        assert checkpoint.signer_key_id == "key_001"

    def test_checkpoint_verify(self) -> None:
        """Audit checkpoint can be verified."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()
        
        now = utc_now()
        checkpoint = create_audit_checkpoint(
            event_window_start=now - timedelta(hours=1),
            event_window_end=now,
            event_count=42,
            event_hash_chain_root=sha256_hex(b"chain_root"),
            private_key=key,
            signer_key_id="key_audit_001",
        )
        
        # Trust the key (simulating trust registry population)
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)
        
        assert checkpoint.verify(registry) is True

    def test_checkpoint_to_dict(self) -> None:
        """Audit checkpoint serializes correctly."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test", key)
        
        now = utc_now()
        checkpoint = AuditCheckpoint(
            checkpoint_id="checkpoint_001",
            timestamp=now,
            event_window_start=now,
            event_window_end=now,
            event_count=10,
            event_hash_chain_root="abc123",
            signature=envelope,
            signer_key_id="key_001",
        )
        
        d = checkpoint.to_dict()
        assert d["checkpoint_id"] == "checkpoint_001"
        assert d["event_count"] == 10
        assert "signature" in d

    def test_checkpoint_failed_verify_revoked_key(self) -> None:
        """Audit checkpoint verification fails for revoked key."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()
        
        now = utc_now()
        checkpoint = create_audit_checkpoint(
            event_window_start=now - timedelta(hours=1),
            event_window_end=now,
            event_count=42,
            event_hash_chain_root=sha256_hex(b"chain_root"),
            private_key=key,
            signer_key_id="key_audit_001",
        )
        
        # Key not trusted - verification should fail
        assert checkpoint.verify(registry) is False
        
        # Revoke after trust - verification should still fail
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)
        registry.revoke_key(checkpoint.signature.public_key_fingerprint_sha256)
        assert registry.is_trusted(checkpoint.signature.public_key_fingerprint_sha256) is False


class TestKeyGenerationAndSigning:
    """Tests for key generation and signing operations."""

    def test_generate_and_load_key(self, tmp_path: object) -> None:
        """Key generation and loading roundtrip works."""
        key_path = generate_private_key(tmp_path / "test_key.pem")  # type: ignore
        
        key = load_private_key(key_path)
        
        # Sign and verify
        envelope = sign_bytes(b"payload", key)
        assert verify_bytes(b"payload", envelope) is True

    def test_sign_bytes_creates_valid_signature(self) -> None:
        """Signing creates verifiable signature."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test data", key)
        
        assert envelope.algorithm == "Ed25519"
        assert envelope.signature_base64 is not None
        assert envelope.public_key_pem is not None
        assert envelope.public_key_fingerprint_sha256 is not None

    def test_verify_bytes_failure_on_wrong_payload(self) -> None:
        """Signature verification fails for wrong payload."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"correct payload", key)
        
        # Verify with wrong payload should fail
        assert verify_bytes(b"wrong payload", envelope) is False

    def test_signature_fingerprint_integrity(self) -> None:
        """Signature envelope fingerprint is bound to the key."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"payload", key)
        
        # Fingerprint should match the public key
        public_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        expected_fingerprint = sha256_hex(public_pem)
        
        assert envelope.public_key_fingerprint_sha256 == expected_fingerprint