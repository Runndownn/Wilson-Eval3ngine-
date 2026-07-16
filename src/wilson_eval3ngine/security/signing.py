"""Signing and key management for Wilson Eval3ngine.

T6.1.3 - Managed secrets, keys, signatures, and audit checkpoints.
Provides Ed25519 signing with key inventory, trust registry integration, and audit checkpoint signing.
"""
from __future__ import annotations

import logging
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..util import new_id, sha256_hex, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    """Container for signature metadata with key fingerprinting."""
    algorithm: str
    public_key_fingerprint_sha256: str
    public_key_pem: str
    signature_base64: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class KeyPurpose(StrEnum):
    """Purpose of a signing key in the hierarchy."""
    SIGNING = "signing"
    ENCRYPTION = "encryption"
    AUDIT = "audit"


@dataclass(frozen=True, slots=True)
class KeyInventoryRecord:
    """Record for key hierarchy inventory tracking.
    
    Tracks all keys with purpose, owner, lifecycle, and recovery information.
    In production, this would be integrated with a KMS/HSM with attestation.
    """
    key_id: str
    purpose: KeyPurpose
    owner: str  # Identity or team responsible
    algorithm: str = "Ed25519"
    
    # Lifecycle
    created_at: datetime = field(default_factory=utc_now)
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    
    # Trust chain
    parent_key_id: str | None = None  # For key rotation chains
    fips_validation: bool = False  # HSM/FIPS validated
    
    # Recovery
    recovery_instructions: str = ""
    
    # State
    active: bool = True
    
    def is_valid(self) -> bool:
        """Check if key is valid for use."""
        if not self.active:
            return False
        if self.revoked_at is not None and utc_now() > self.revoked_at:
            return False
        if self.expires_at is not None and utc_now() > self.expires_at:
            return False
        return True


@dataclass(frozen=True, slots=True)
class AuditCheckpoint:
    """Signed audit checkpoint for immutable event logging.
    
    Creates a cryptographic checkpoint of system state that can be verified
    independently and used for integrity verification across points in time.
    """
    checkpoint_id: str
    timestamp: datetime
    event_window_start: datetime
    event_window_end: datetime
    event_count: int
    event_hash_chain_root: str
    signature: SignatureEnvelope
    signer_key_id: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp.isoformat(),
            "event_window_start": self.event_window_start.isoformat(),
            "event_window_end": self.event_window_end.isoformat(),
            "event_count": self.event_count,
            "event_hash_chain_root": self.event_hash_chain_root,
            "signature": self.signature.to_dict(),
            "signer_key_id": self.signer_key_id,
        }
    
    def verify(self, trust_registry: TrustRegistry) -> bool:
        """Verify checkpoint signature against trust registry."""
        if not trust_registry.is_trusted(self.signature.public_key_fingerprint_sha256):
            return False
        # Verify the checkpoint data integrity using the same payload used for signing
        payload = f"{self.event_count}|{self.event_hash_chain_root}"
        return verify_bytes(payload.encode(), self.signature)
    
    def _canonical_payload(self) -> str:
        """Generate canonical string for signature verification."""
        # This matches the payload used in create_audit_checkpoint
        return f"{self.event_count}|{self.event_hash_chain_root}"


@dataclass
class KeyInventory:
    """Manages key inventory for rotation and recovery tracking.
    
    In production, this would integrate with external KMS. For MVP,
    provides in-memory tracking with export capability.
    """
    
    def __init__(self) -> None:
        self._keys: dict[str, KeyInventoryRecord] = {}
    
    def register_key(
        self,
        key_id: str,
        purpose: KeyPurpose,
        owner: str,
        *,
        parent_key_id: str | None = None,
        expires_at: datetime | None = None,
        recovery_instructions: str = "",
    ) -> KeyInventoryRecord:
        """Register a key in the inventory."""
        record = KeyInventoryRecord(
            key_id=key_id,
            purpose=purpose,
            owner=owner,
            parent_key_id=parent_key_id,
            expires_at=expires_at,
            recovery_instructions=recovery_instructions,
        )
        self._keys[key_id] = record
        logger.info(
            "key_registered",
            extra={"key_id": key_id, "purpose": purpose, "owner": owner}
        )
        return record
    
    def get_key(self, key_id: str) -> KeyInventoryRecord | None:
        """Get a key record by ID."""
        return self._keys.get(key_id)
    
    def rotate_key(
        self,
        old_key_id: str,
        new_key_id: str,
        purpose: KeyPurpose,
        owner: str,
        expires_at: datetime | None = None,
    ) -> KeyInventoryRecord:
        """Record a key rotation event."""
        return self.register_key(
            new_key_id,
            purpose,
            owner,
            parent_key_id=old_key_id,
            expires_at=expires_at,
        )
    
    def revoke_key(self, key_id: str) -> None:
        """Revoke a key in the inventory."""
        record = self._keys.get(key_id)
        if record:
            # Keys are immutable - we store revocation as a new record
            revoked = KeyInventoryRecord(
                key_id=record.key_id,
                purpose=record.purpose,
                owner=record.owner,
                algorithm=record.algorithm,
                created_at=record.created_at,
                activated_at=record.activated_at,
                expires_at=record.expires_at,
                revoked_at=utc_now(),
                parent_key_id=record.parent_key_id,
                fips_validation=record.fips_validation,
                recovery_instructions=record.recovery_instructions,
                active=False,
            )
            self._keys[key_id] = revoked
            logger.warning(
                "key_revoked",
                extra={"key_id": key_id}
            )
    
    def list_active_keys(self, purpose: KeyPurpose | None = None) -> list[KeyInventoryRecord]:
        """List all active keys, optionally filtered by purpose."""
        keys = [k for k in self._keys.values() if k.active and k.is_valid()]
        if purpose:
            keys = [k for k in keys if k.purpose == purpose]
        return keys


class TrustRegistry:
    """Trusted key registry for signature verification.
    
    In production, this would integrate with an external PKI/vault.
    Maintains trust status for key fingerprints across time.
    """

    def __init__(self) -> None:
        self._trusted_fingerprints: set[str] = set()
        self._revoked_fingerprints: set[str] = set()

    def trust_key(self, fingerprint_sha256: str) -> None:
        """Add a key fingerprint to the trusted registry."""
        self._trusted_fingerprints.add(fingerprint_sha256)
        self._revoked_fingerprints.discard(fingerprint_sha256)

    def is_trusted(self, fingerprint_sha256: str) -> bool:
        """Check if a key fingerprint is trusted (not revoked)."""
        if fingerprint_sha256 in self._revoked_fingerprints:
            return False
        return fingerprint_sha256 in self._trusted_fingerprints

    def revoke_key(self, fingerprint_sha256: str) -> None:
        """Remove a key from the trusted registry."""
        self._revoked_fingerprints.add(fingerprint_sha256)
        self._trusted_fingerprints.discard(fingerprint_sha256)


def generate_private_key(path: str | Path) -> Path:
    """Generate a new Ed25519 private key."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    target.write_bytes(pem)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def load_private_key(path: str | Path) -> Ed25519PrivateKey:
    """Load a private key from PEM file."""
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("signing key must be Ed25519")
    return key


def sign_bytes(payload: bytes, private_key: Ed25519PrivateKey) -> SignatureEnvelope:
    """Sign bytes with an Ed25519 private key."""
    public = private_key.public_key()
    public_bytes = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = private_key.sign(payload)
    return SignatureEnvelope(
        algorithm="Ed25519",
        public_key_fingerprint_sha256=sha256_hex(public_bytes),
        public_key_pem=public_bytes.decode("ascii"),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def verify_bytes(payload: bytes, envelope: SignatureEnvelope) -> bool:
    """Verify signature against payload."""
    try:
        public = serialization.load_pem_public_key(envelope.public_key_pem.encode("ascii"))
        if not isinstance(public, Ed25519PublicKey):
            return False
        if sha256_hex(envelope.public_key_pem.encode("ascii")) != (
            envelope.public_key_fingerprint_sha256
        ):
            return False
        public.verify(b64decode(envelope.signature_base64), payload)
        return True
    except Exception:
        return False


def create_audit_checkpoint(
    event_window_start: datetime,
    event_window_end: datetime,
    event_count: int,
    event_hash_chain_root: str,
    private_key: Ed25519PrivateKey,
    signer_key_id: str,
) -> AuditCheckpoint:
    """Create a signed audit checkpoint.
    
    Args:
        event_window_start: Start of event window
        event_window_end: End of event window
        event_count: Number of events in window
        event_hash_chain_root: Root hash of hash chain
        private_key: Key to sign with
        signer_key_id: ID of signing key
        
    Returns:
        Signed checkpoint record
    """
    checkpoint = AuditCheckpoint(
        checkpoint_id=new_id("checkpoint"),
        timestamp=utc_now(),
        event_window_start=event_window_start,
        event_window_end=event_window_end,
        event_count=event_count,
        event_hash_chain_root=event_hash_chain_root,
        signature=sign_bytes(
            f"{event_count}|{event_hash_chain_root}".encode(),
            private_key,
        ),
        signer_key_id=signer_key_id,
    )
    logger.info(
        "audit_checkpoint_created",
        extra={
            "checkpoint_id": checkpoint.checkpoint_id,
            "event_count": event_count,
            "signer_key_id": signer_key_id,
        }
    )
    return checkpoint


__all__ = [
    "SignatureEnvelope",
    "KeyPurpose",
    "KeyInventoryRecord",
    "AuditCheckpoint",
    "KeyInventory",
    "TrustRegistry",
    "generate_private_key",
    "load_private_key",
    "sign_bytes",
    "verify_bytes",
    "create_audit_checkpoint",
]
