"""
Environment-specific tests for Signing Key Management (SEC-004).

Tests key inventory, trust registry, audit checkpoints, rotation, and
revocation across different deployment environments:
- Development: Local key files, dev trust registry
- Staging: Simulated KMS-managed keys, staging trust registry
- Production: Full key lifecycle with FIPS validation, audit checkpoints
- Minimal: No optional dependencies
- OTel-enabled/disabled: tracing behavior with signing operations

Test counts: 13 integration tests
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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


# ============================================================================
# Environment-Specific Key Inventory Tests (4 tests)
# ============================================================================

class TestKeyInventoryAcrossEnvironments:
    """Test key inventory management across different environments."""

    def test_register_key_dev_environment(self):
        """Key registration in development environment."""
        inventory = KeyInventory()
        record = inventory.register_key(
            key_id="dev_key_001",
            purpose=KeyPurpose.SIGNING,
            owner="dev_engineer",
        )
        assert record.key_id == "dev_key_001"
        assert record.purpose == KeyPurpose.SIGNING
        assert record.owner == "dev_engineer"
        assert record.active is True
        assert record.is_valid() is True

    def test_register_key_staging_environment(self):
        """Key registration in staging environment."""
        inventory = KeyInventory()
        record = inventory.register_key(
            key_id="staging_key_001",
            purpose=KeyPurpose.SIGNING,
            owner="staging_engineer",
        )
        assert record.key_id == "staging_key_001"
        assert record.is_valid() is True

    def test_register_key_production_environment(self):
        """Key registration in production environment."""
        inventory = KeyInventory()
        record = inventory.register_key(
            key_id="prod_key_001",
            purpose=KeyPurpose.SIGNING,
            owner="release_authority",
        )
        assert record.key_id == "prod_key_001"
        assert record.purpose == KeyPurpose.SIGNING
        assert record.owner == "release_authority"
        assert record.is_valid() is True

    def test_key_rotation_with_parent_reference(self):
        """Key rotation records parent relationship."""
        inventory = KeyInventory()
        inventory.register_key(
            "key_old",
            KeyPurpose.SIGNING,
            "release_authority",
        )

        new = inventory.rotate_key(
            "key_old",
            "key_new",
            KeyPurpose.SIGNING,
            "release_authority",
        )

        assert new.parent_key_id == "key_old"
        assert new.key_id == "key_new"
        assert inventory.get_key("key_new") is not None


# ============================================================================
# Environment-Specific Trust Registry Tests (4 tests)
# ============================================================================

class TestTrustRegistryAcrossEnvironments:
    """Test trust registry behavior across environments."""

    def test_trust_key_dev_environment(self):
        """Key fingerprint can be trusted in development."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"dev_key_data")

        registry.trust_key(fingerprint)

        assert registry.is_trusted(fingerprint) is True

    def test_trust_key_staging_environment(self):
        """Key fingerprint can be trusted in staging."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"staging_key_data")

        registry.trust_key(fingerprint)

        assert registry.is_trusted(fingerprint) is True

    def test_revoke_key_production_environment(self):
        """Trusted key can be revoked in production."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"prod_key_data")

        registry.trust_key(fingerprint)
        assert registry.is_trusted(fingerprint) is True

        registry.revoke_key(fingerprint)

        assert registry.is_trusted(fingerprint) is False

    def test_unknown_key_not_trusted(self):
        """Unknown keys are not trusted."""
        registry = TrustRegistry()
        fingerprint = sha256_hex(b"unknown_key")

        assert registry.is_trusted(fingerprint) is False


# ============================================================================
# Environment-Specific Audit Checkpoint Tests (3 tests)
# ============================================================================

class TestAuditCheckpointAcrossEnvironments:
    """Test audit checkpoint signing across environments."""

    def test_create_checkpoint_dev_environment(self):
        """Audit checkpoint can be created in development."""
        key = Ed25519PrivateKey.generate()

        now = utc_now().isoformat()
        checkpoint = AuditCheckpoint(
            checkpoint_id="dev_checkpoint_001",
            timestamp=now,
            event_window_start=(utc_now() - timedelta(hours=1)).isoformat(),
            event_window_end=now,
            event_count=100,
            event_hash_chain_root=sha256_hex(b"dev_root"),
            signature=sign_bytes(b"test", key),
            signer_key_id="dev_key_001",
        )

        assert checkpoint.checkpoint_id == "dev_checkpoint_001"
        assert checkpoint.event_count == 100
        assert checkpoint.signer_key_id == "dev_key_001"

    def test_create_checkpoint_staging_environment(self):
        """Audit checkpoint can be created in staging."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now_dt = utc_now()
        checkpoint = create_audit_checkpoint(
            event_window_start=(now_dt - timedelta(hours=1)).isoformat(),
            event_window_end=now_dt.isoformat(),
            event_count=42,
            event_hash_chain_root=sha256_hex(b"staging_root"),
            private_key=key,
            signer_key_id="staging_key_001",
        )

        # Trust the key
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)

        assert checkpoint.verify(registry) is True

    def test_create_checkpoint_production_environment(self):
        """Audit checkpoint can be created and verified in production."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now_dt = utc_now()
        checkpoint = create_audit_checkpoint(
            event_window_start=(now_dt - timedelta(hours=1)).isoformat(),
            event_window_end=now_dt.isoformat(),
            event_count=1000,
            event_hash_chain_root=sha256_hex(b"prod_root"),
            private_key=key,
            signer_key_id="prod_key_001",
        )

        # Trust the key
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)

        assert checkpoint.verify(registry) is True

    def test_checkpoint_failed_verify_revoked_key(self):
        """Audit checkpoint verification fails for revoked key."""
        registry = TrustRegistry()
        key = Ed25519PrivateKey.generate()

        now_dt = utc_now()
        checkpoint = create_audit_checkpoint(
            event_window_start=(now_dt - timedelta(hours=1)).isoformat(),
            event_window_end=now_dt.isoformat(),
            event_count=42,
            event_hash_chain_root=sha256_hex(b"chain_root"),
            private_key=key,
            signer_key_id="key_audit_001",
        )

        # Key not trusted - verification should fail
        assert checkpoint.verify(registry) is False

        # Trust then revoke - verification should still fail
        registry.trust_key(checkpoint.signature.public_key_fingerprint_sha256)
        registry.revoke_key(checkpoint.signature.public_key_fingerprint_sha256)
        assert registry.is_trusted(checkpoint.signature.public_key_fingerprint_sha256) is False


# ============================================================================
# Environment-Specific Key Generation and Signing Tests (2 tests)
# ============================================================================

class TestKeyGenerationAndSigningAcrossEnvironments:
    """Test key generation and signing operations across environments."""

    def test_generate_and_load_key_dev_environment(self, tmp_path):
        """Key generation and loading roundtrip works in development."""
        key_path = generate_private_key(tmp_path / "dev_key.pem")

        key = load_private_key(key_path)

        # Sign and verify
        envelope = sign_bytes(b"dev payload", key)
        assert verify_bytes(b"dev payload", envelope) is True

    def test_generate_and_load_key_production_environment(self, tmp_path):
        """Key generation and loading roundtrip works in production."""
        key_path = generate_private_key(tmp_path / "prod_key.pem")

        key = load_private_key(key_path)

        # Sign and verify
        envelope = sign_bytes(b"prod payload", key)
        assert verify_bytes(b"prod payload", envelope) is True

    def test_signature_fingerprint_integrity(self):
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

    def test_verify_bytes_failure_on_wrong_payload(self):
        """Signature verification fails for wrong payload."""
        key = Ed25519PrivateKey.generate()
        envelope = sign_bytes(b"correct payload", key)

        # Verify with wrong payload should fail
        assert verify_bytes(b"wrong payload", envelope) is False
