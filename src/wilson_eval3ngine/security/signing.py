from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..util import sha256_hex, utc_now


class KeyPurpose(str, Enum):
    """Key purpose enumeration for key inventory."""
    SIGNING = "signing"
    AUDIT = "audit"
    ENCRYPTION = "encryption"


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    algorithm: str
    public_key_fingerprint_sha256: str
    public_key_pem: str
    signature_base64: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AuditCheckpoint:
    """Audit checkpoint for event verification."""
    checkpoint_id: str
    timestamp: str
    event_window_start: str
    event_window_end: str
    event_count: int
    event_hash_chain_root: str
    signature: SignatureEnvelope
    signer_key_id: str

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp,
            "event_window_start": self.event_window_start,
            "event_window_end": self.event_window_end,
            "event_count": self.event_count,
            "event_hash_chain_root": self.event_hash_chain_root,
            "signature": self.signature.to_dict(),
            "signer_key_id": self.signer_key_id,
        }

    def verify(self, registry: "TrustRegistry") -> bool:
        """Verify checkpoint signature against trust registry."""
        if not registry.is_trusted(self.signature.public_key_fingerprint_sha256):
            return False
        # Verify the signature covers the canonical payload
        payload = self._canonical_payload()
        return verify_bytes(payload.encode(), self.signature)

    def _canonical_payload(self) -> str:
        """Produce canonical payload for signature verification."""
        return f"{self.timestamp}:{self.event_count}:{self.event_hash_chain_root}"


def generate_private_key(path: str | Path) -> Path:
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
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("signing key must be Ed25519")
    return key


def sign_bytes(payload: bytes, private_key: Ed25519PrivateKey) -> SignatureEnvelope:
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


# ============================================================================
# Trust Registry
# ============================================================================

class TrustRegistry:
    """Trust registry for key fingerprint management."""

    def __init__(self) -> None:
        self._trusted_fingerprints: set[str] = set()
        self._revoked_fingerprints: set[str] = set()

    def trust_key(self, fingerprint_sha256: str) -> None:
        """Add a key fingerprint to the trusted set."""
        self._trusted_fingerprints.add(fingerprint_sha256)
        self._revoked_fingerprints.discard(fingerprint_sha256)

    def revoke_key(self, fingerprint_sha256: str) -> None:
        """Remove a key from trust (revoke)."""
        self._revoked_fingerprints.add(fingerprint_sha256)
        self._trusted_fingerprints.discard(fingerprint_sha256)

    def is_trusted(self, fingerprint_sha256: str) -> bool:
        """Check if a key fingerprint is currently trusted."""
        return (
            fingerprint_sha256 in self._trusted_fingerprints
            and fingerprint_sha256 not in self._revoked_fingerprints
        )


# ============================================================================
# Key Inventory
# ============================================================================

@dataclass
class KeyRecord:
    """Key record in the inventory."""
    key_id: str
    purpose: KeyPurpose
    owner: str
    created_at: str
    active: bool = True
    expires_at: str | None = None
    parent_key_id: str | None = None
    fips_validation: bool = False

    def is_valid(self) -> bool:
        """Check if key record is currently valid."""
        if not self.active:
            return False
        if self.expires_at is not None:
            expires_dt = datetime.fromisoformat(self.expires_at)
            if expires_dt < datetime.now(expires_dt.tzinfo or None):
                return False
        return True


def create_audit_checkpoint(
    event_window_start: str,
    event_window_end: str,
    event_count: int,
    event_hash_chain_root: str,
    private_key: Ed25519PrivateKey,
    signer_key_id: str,
) -> AuditCheckpoint:
    """Create an audit checkpoint with signature."""
    now = utc_now().isoformat()
    checkpoint_id = f"checkpoint_{sha256_hex(now)[:16]}"
    envelope = sign_bytes(f"{now}:{event_count}:{event_hash_chain_root}".encode(), private_key)
    return AuditCheckpoint(
        checkpoint_id=checkpoint_id,
        timestamp=now,
        event_window_start=event_window_start,
        event_window_end=event_window_end,
        event_count=event_count,
        event_hash_chain_root=event_hash_chain_root,
        signature=envelope,
        signer_key_id=signer_key_id,
    )


class KeyInventory:
    """Key inventory for managing signing/Audit keys."""

    def __init__(self) -> None:
        self._keys: dict[str, KeyRecord] = {}

    def register_key(
        self,
        key_id: str,
        purpose: KeyPurpose,
        owner: str,
        expires_at: datetime | None = None,
    ) -> KeyRecord:
        """Register a new key in the inventory."""
        record = KeyRecord(
            key_id=key_id,
            purpose=purpose,
            owner=owner,
            created_at=utc_now(),
            expires_at=expires_at.isoformat() if expires_at else None,
        )
        self._keys[key_id] = record
        return record

    def get_key(self, key_id: str) -> KeyRecord | None:
        """Retrieve a key record by ID."""
        return self._keys.get(key_id)

    def rotate_key(
        self,
        old_key_id: str,
        new_key_id: str,
        purpose: KeyPurpose,
        owner: str,
    ) -> KeyRecord:
        """Create a new key with parent reference."""
        if old_key_id not in self._keys:
            raise ValueError(f"Old key {old_key_id} not found")
        new_record = KeyRecord(
            key_id=new_key_id,
            purpose=purpose,
            owner=owner,
            created_at=utc_now(),
            parent_key_id=old_key_id,
        )
        self._keys[new_key_id] = new_record
        return new_record

    def revoke_key(self, key_id: str) -> None:
        """Mark a key as inactive."""
        if key_id in self._keys:
            record = self._keys[key_id]
            # Create new record with active=False
            self._keys[key_id] = KeyRecord(
                key_id=record.key_id,
                purpose=record.purpose,
                owner=record.owner,
                created_at=record.created_at,
                active=False,
                expires_at=record.expires_at,
                parent_key_id=record.parent_key_id,
                fips_validation=record.fips_validation,
            )

    def list_active_keys(self, purpose: KeyPurpose | None = None) -> list[KeyRecord]:
        """List all active (non-expired) keys, optionally filtered by purpose."""
        active = [k for k in self._keys.values() if k.is_valid()]
        if purpose:
            active = [k for k in active if k.purpose == purpose]
        return active


__all__ = [
    "KeyPurpose",
    "SignatureEnvelope",
    "AuditCheckpoint",
    "TrustRegistry",
    "KeyInventory",
    "KeyRecord",
    "create_audit_checkpoint",
    "generate_private_key",
    "load_private_key",
    "sign_bytes",
    "verify_bytes",
]
