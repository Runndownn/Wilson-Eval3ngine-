"""Integration tests for key management, signing, and audit checkpoints (TODO 40).

Tests cover:
- Key inventory integration with trust registry
- Audit checkpoint creation and verification workflow
- Key rotation with historical signature verification
- Signature verification failure scenarios
- Key revocation and trust status propagation
"""

from __future__ import annotations

from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from wilson_eval3ngine.security.signing import (
    AuditCheckpoint,
    KeyInventory,
    KeyPurpose,
    TrustRegistry,
    create_audit_checkpoint,
    sign_bytes,
    verify_bytes,
)
from wilson_eval3ngine.util import sha256_hex, utc_now


class TestKeyInventoryTrustRegistryIntegration:
    """Integration tests for key inventory and trust registry."""

    def test_key_trust_lifecycle(self) -> None:
        """Key can be registered, trusted, revoked, and verified."""
        inventory = KeyInventory()
        registry = TrustRegistry()

        # Register a signing key
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test payload", key)
        fingerprint = envelope.public_key_fingerprint_sha256

        inventory.register_key(
            key_id="signing_001",
            purpose=KeyPurpose.SIGNING,
            owner="release_authority",
        )

        # Initially not trusted
        assert registry.is_trusted(fingerprint) is False

        # Trust the key
        registry.trust_key(fingerprint)
        assert verify_bytes(b"test payload", envelope) is True

        # Revoke trust
        registry.revoke_key(fingerprint)
        assert registry.is_trusted(fingerprint) is False

    def test_key_rotation_preserves_parent_chain(self) -> None:
        """Key rotation maintains parent relationship for lineage."""
        inventory = KeyInventory()

        # Register old key
        inventory.register_key(
            key_id="signing_old",
            purpose=KeyPurpose.SIGNING,
            owner="release_authority",
        )

        # Generate and register new key with parent reference
        new_record = inventory.rotate_key(
            old_key_id="signing_old",
            new_key_id="signing_new",
            purpose=KeyPurpose.SIGNING,
            owner="release_authority",
        )

        # Verify parent chain
        assert new_record.parent_key_id == "signing_old"
        assert inventory.get_key("signing_old") is not None  # Old key still exists
        assert inventory.get_key("signing_new") is not None

    def test_history_verification_with_secondary_registry(self) -> None:
        """Historical signatures can be verified against secondary trust registry."""
        registry = TrustRegistry()

        # Create checkpoint with first key
        key_a = Ed25519PrivateKey.generate()
        envelope_a = sign_bytes(b"data_a", key_a)
        fingerprint_a = envelope_a.public_key_fingerprint_sha256

        # Trust key A
        registry.trust_key(fingerprint_a)

        # Verify works
        assert verify_bytes(b"data_a", envelope_a) is True

        # Now create checkpoint with different key, trust it too
        key_b = Ed25519PrivateKey.generate()
        envelope_b = sign_bytes(b"data_b", key_b)
        fingerprint_b = envelope_b.public_key_fingerprint_sha256

        registry.trust_key(fingerprint_b)
        assert verify_bytes(b"data_b", envelope_b) is True

        # Both historical signatures still verifiable
        assert registry.is_trusted(fingerprint_a) is True
        assert registry.is_trusted(fingerprint_b) is True


class TestAuditCheckpointWorkflow:
    """Integration tests for audit checkpoint lifecycle."""

    def test_full_checkpoint_workflow(self) -> None:
        """Audit checkpoint creation and verification workflow end-to-end."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now = utc_now().isoformat()
        window_start = (utc_now() - timedelta(hours=1)).isoformat()
        window_end = now

        # Create checkpoint
        checkpoint = create_audit_checkpoint(
            event_window_start=window_start,
            event_window_end=window_end,
            event_count=42,
            event_hash_chain_root=sha256_hex(b"hash_chain_root"),
            private_key=key,
            signer_key_id="audit_key_001",
        )

        # Trust the signing key
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)

        # Verify checkpoint
        assert checkpoint.verify(registry) is True

        # Verify serialized form
        d = checkpoint.to_dict()
        assert d["event_count"] == 42
        assert d["signer_key_id"] == "audit_key_001"
        assert "signature" in d

    def test_multiple_checkpoints_chain(self) -> None:
        """Multiple checkpoints can be created and verified in sequence."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        checkpoints = []
        for i in range(3):
            now = utc_now().isoformat()
            start = (utc_now() - timedelta(hours=1)).isoformat()
            checkpoint = create_audit_checkpoint(
                event_window_start=start,
                event_window_end=now,
                event_count=i * 100,
                event_hash_chain_root=sha256_hex(f"chain_{i}".encode()),
                private_key=key,
                signer_key_id="audit_key_001",
            )
            checkpoints.append(checkpoint)

        # Trust key once
        registry.trust_key(checkpoints[0].signature.public_key_fingerprint_sha256)

        # All checkpoints verifiable
        for i, cp in enumerate(checkpoints):
            assert cp.verify(registry) is True, f"Checkpoint {i} failed verification"

    def test_checkpoint_verification_fails_without_trust(self) -> None:
        """Checkpoint verification fails if key not in trust registry."""
        key = Ed25519PrivateKey.generate()
        now = utc_now().isoformat()
        start = (utc_now() - timedelta(hours=1)).isoformat()

        checkpoint = create_audit_checkpoint(
            event_window_start=start,
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"root"),
            private_key=key,
            signer_key_id="audit_key_001",
        )

        registry = TrustRegistry()  # No keys trusted

        # Verification should fail
        assert checkpoint.verify(registry) is False


class TestKeyRevocationImpact:
    """Tests for key revocation impact on signatures and checkpoints."""

    def test_revoked_key_checkpoints_fail(self) -> None:
        """Revoked key causes checkpoint verification to fail."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now = utc_now().isoformat()
        start = (utc_now() - timedelta(hours=1)).isoformat()
        # Create checkpoint
        checkpoint = create_audit_checkpoint(
            event_window_start=start,
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"root"),
            private_key=key,
            signer_key_id="revoked_key",
        )

        fingerprint = checkpoint.signature.public_key_fingerprint_sha256

        # Initially trusted
        registry.trust_key(fingerprint)
        assert checkpoint.verify(registry) is True

        # Revoke and verify fails
        registry.revoke_key(fingerprint)
        assert checkpoint.verify(registry) is False

    def test_revoked_key_signing_fails(self) -> None:
        """Signature verification fails with revoked key."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        envelope = sign_bytes(b"payload", key)
        fingerprint = envelope.public_key_fingerprint_sha256

        # Trust then revoke
        registry.trust_key(fingerprint)
        registry.revoke_key(fingerprint)

        # Raw verification still works (signature valid), but trust check fails
        assert verify_bytes(b"payload", envelope) is True  # Signature ok
        assert registry.is_trusted(fingerprint) is False  # But not trusted


class TestAuditIntegrity:
    """Tests for audit integrity through signature tampering detection."""

    def test_tampered_checkpoint_detected(self) -> None:
        """Tampered checkpoint event count fails verification."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now = utc_now().isoformat()
        start = (utc_now() - timedelta(hours=1)).isoformat()
        original = create_audit_checkpoint(
            event_window_start=start,
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"root"),
            private_key=key,
            signer_key_id="audit_key",
        )

        # Trust the key
        registry.trust_key(original.signature.public_key_fingerprint_sha256)

        # Create tampered checkpoint (same signature, different event_count)
        tampered = AuditCheckpoint(
            checkpoint_id=original.checkpoint_id,
            timestamp=original.timestamp,
            event_window_start=original.event_window_start,
            event_window_end=original.event_window_end,
            event_count=999,  # Changed!
            event_hash_chain_root=original.event_hash_chain_root,
            signature=original.signature,
            signer_key_id=original.signer_key_id,
        )

        # Verification should fail due to tampering
        assert tampered.verify(registry) is False

    def test_hash_chain_integrity(self) -> None:
        """Hash chain root changes break verification."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now = utc_now().isoformat()
        start = (utc_now() - timedelta(hours=1)).isoformat()
        original = create_audit_checkpoint(
            event_window_start=start,
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"original_root"),
            private_key=key,
            signer_key_id="audit_key",
        )

        registry.trust_key(original.signature.public_key_fingerprint_sha256)
        assert original.verify(registry) is True

        # Create with wrong hash chain
        tampered = AuditCheckpoint(
            checkpoint_id=original.checkpoint_id,
            timestamp=original.timestamp,
            event_window_start=original.event_window_start,
            event_window_end=original.event_window_end,
            event_count=original.event_count,
            event_hash_chain_root=sha256_hex(b"wrong_root"),  # Changed!
            signature=original.signature,
            signer_key_id=original.signer_key_id,
        )

        assert tampered.verify(registry) is False


class TestSignatureFormatSecurity:
    """Tests for signature format security properties."""

    def test_signature_envelope_contains_all_metadata(self) -> None:
        """Signature envelope includes all required verification metadata."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"test data", key)

        # Algorithm specified
        assert envelope.algorithm == "Ed25519"

        # Public key fingerprint for key identification
        assert len(envelope.public_key_fingerprint_sha256) == 64  # SHA-256 hex

        # Public key PEM included for verification
        assert "-----BEGIN PUBLIC KEY-----" in envelope.public_key_pem
        assert "-----END PUBLIC KEY-----" in envelope.public_key_pem

        # Signature is base64 encoded
        assert envelope.signature_base64 is not None
        assert len(envelope.signature_base64) > 0

    def test_fingerprint_uniqueness(self) -> None:
        """Different keys produce different fingerprints."""
        key_a = Ed25519PrivateKey.generate()
        key_b = Ed25519PrivateKey.generate()

        envelope_a = sign_bytes(b"test", key_a)
        envelope_b = sign_bytes(b"test", key_b)

        # Same payload, different keys = different fingerprints
        assert envelope_a.public_key_fingerprint_sha256 != envelope_b.public_key_fingerprint_sha256

    def test_canonical_payload_deterministic(self) -> None:
        """Same inputs produce same canonical payload for signing."""
        key = Ed25519PrivateKey.generate()

        # Same inputs should produce same signature
        sig1 = sign_bytes(b"same payload", key)
        sig2 = sign_bytes(b"same payload", key)

        assert sig1.signature_base64 == sig2.signature_base64
        assert sig1.public_key_fingerprint_sha256 == sig2.public_key_fingerprint_sha256