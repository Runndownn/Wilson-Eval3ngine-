"""Encrypted object storage for evidence protection at rest.

SEC-006: Encrypted object storage with KMS-backed encryption and retention policies.

This module provides:
1. AES-256-GCM encryption of artifact content at rest
2. KMS-managed data encryption keys (envelope encryption)
3. Retention policy enforcement (legal hold, minimum retention)
4. Immutable content-addressed storage
5. Project-scoped access control

Encryption flow (envelope encryption):
1. On first use, generate a data encryption key (DEK) using AES-256
2. Encrypt the DEK with a KMS-managed master key
3. Store the encrypted DEK alongside the artifact metadata
4. Encrypt artifact content with the DEK using AES-256-GCM
5. Store encrypted content + authentication tag
6. On retrieval, decrypt DEK with KMS, then decrypt content

For development/testing, a local key derivation function is used instead of KMS.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..util import sha256_hex, utc_now

logger = logging.getLogger("wilson.storage.encrypted")


# Retention policy constants
DEFAULT_MIN_RETENTION_DAYS = 365  # 1 year minimum
DEFAULT_MAX_RETENTION_DAYS = 1825  # 5 years maximum
LEGAL_HOLD_RETENTION_DAYS = 36500  # 100 years for legal hold


class EncryptionError(Exception):
    """Raised when encryption/decryption operations fail."""
    pass


class RetentionViolationError(Exception):
    """Raised when a retention policy violation is detected."""
    pass


class KeyManagementError(Exception):
    """Raised when KMS key management operations fail."""
    pass


@dataclass(frozen=True, slots=True)
class EncryptedArtifactRef:
    """Reference to an encrypted artifact."""
    project_id: str
    sha256: str
    media_type: str
    size_bytes: int
    relative_path: str
    created_at: str
    # Encryption metadata
    encryption_key_id: str
    encrypted_dek: str  # Base64-encoded encrypted data encryption key
    iv: str  # Base64-encoded initialization vector
    auth_tag: str  # Base64-encoded authentication tag
    retention_policy: str
    retention_expires_at: str | None
    legal_hold: bool


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Retention policy for encrypted artifacts."""
    policy_id: str
    min_retention_days: int
    max_retention_days: int
    legal_hold: bool
    classification: str  # "public", "internal", "confidential", "restricted"

    @classmethod
    def default(cls, classification: str = "confidential") -> "RetentionPolicy":
        """Get the default retention policy for a classification."""
        policies = {
            "public": cls(
                policy_id="retention:public:default",
                min_retention_days=90,
                max_retention_days=365,
                legal_hold=False,
                classification="public",
            ),
            "internal": cls(
                policy_id="retention:internal:default",
                min_retention_days=365,
                max_retention_days=1095,
                legal_hold=False,
                classification="internal",
            ),
            "confidential": cls(
                policy_id="retention:confidential:default",
                min_retention_days=DEFAULT_MIN_RETENTION_DAYS,
                max_retention_days=DEFAULT_MAX_RETENTION_DAYS,
                legal_hold=False,
                classification="confidential",
            ),
            "restricted": cls(
                policy_id="retention:restricted:default",
                min_retention_days=DEFAULT_MAX_RETENTION_DAYS,
                max_retention_days=LEGAL_HOLD_RETENTION_DAYS,
                legal_hold=True,
                classification="restricted",
            ),
        }
        return policies.get(classification, policies["confidential"])


class KMSClient(Protocol):
    """Protocol for KMS key management operations."""

    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        """Encrypt data with a KMS-managed key."""
        ...

    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        """Decrypt data with a KMS-managed key."""
        ...

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        """Generate a data encryption key.

        Returns:
            Tuple of (plaintext_dek, encrypted_dek)
        """
        ...


class LocalKMSClient:
    """Local KMS client for development and testing.

    Uses HKDF to derive encryption keys from a master key.
    NOT SUITABLE FOR PRODUCTION - use a real KMS in production.
    """

    def __init__(self, master_key: bytes | None = None):
        if master_key is None:
            master_key = os.environ.get("WE3_KMS_MASTER_KEY", "").encode("utf-8")
        if len(master_key) < 32:
            raise KeyManagementError(
                "Master key must be at least 32 bytes. "
                "Set WE3_KMS_MASTER_KEY environment variable."
            )
        self._master_key = master_key

    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        """Encrypt data using HKDF-derived key (development only)."""
        derived_key = self._derive_key(key_id)
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(derived_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        """Decrypt data using HKDF-derived key (development only)."""
        derived_key = self._derive_key(key_id)
        nonce = ciphertext[:12]
        encrypted_data = ciphertext[12:]
        aesgcm = AESGCM(derived_key)
        return aesgcm.decrypt(nonce, encrypted_data, None)

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        """Generate a random data encryption key."""
        dek = secrets.token_bytes(32)  # 256-bit DEK
        encrypted_dek = self.encrypt(key_id, dek)
        return dek, encrypted_dek

    def _derive_key(self, key_id: str) -> bytes:
        """Derive a key from the master key using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=key_id.encode("utf-8"),
            info=b"wilson-kms-v1",
        )
        return hkdf.derive(self._master_key)


class EncryptedObjectStore:
    """Encrypted object store with KMS-backed encryption and retention.

    Artifacts are:
    - Encrypted at rest using AES-256-GCM
    - Protected by envelope encryption (KMS-managed DEK)
    - Content-addressed by SHA-256
    - Scoped by project_id and classification
    - Retention policy enforced
    - Immutable (write-once by hash)

    Args:
        root: Storage root directory
        kms_client: KMS client for key management
        kms_key_id: KMS key ID for envelope encryption
        default_retention: Default retention policy
    """

    MAX_PAYLOAD_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(
        self,
        root: str | Path,
        kms_client: KMSClient,
        kms_key_id: str,
        default_retention: RetentionPolicy | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.kms_client = kms_client
        self.kms_key_id = kms_key_id
        self.default_retention = default_retention or RetentionPolicy.default("confidential")

    def _validate_project(self, project_id: str) -> str:
        """Validate project ID for path safety."""
        import re
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$", project_id):
            raise ValueError("invalid project_id for artifact path")
        return project_id

    def _payload_path(self, project_id: str, digest: str) -> Path:
        """Get the content-addressed path for an artifact."""
        project = self._validate_project(project_id)
        return self.root / project / "sha256" / digest[:2] / digest

    def _metadata_path(self, project_id: str, digest: str) -> Path:
        """Get the metadata path for an artifact."""
        return self._payload_path(project_id, digest).with_suffix(".encrypted.json")

    def _encrypt_payload(
        self,
        payload: bytes,
        retention: RetentionPolicy,
    ) -> tuple[bytes, str, str, str]:
        """Encrypt payload using envelope encryption.

        Returns:
            Tuple of (encrypted_payload, encrypted_dek_b64, iv_b64, auth_tag_b64)
        """
        # Generate data encryption key
        dek, encrypted_dek = self.kms_client.generate_data_key(self.kms_key_id)

        # Encrypt payload with DEK
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(dek)
        encrypted_payload = aesgcm.encrypt(nonce, payload, None)

        # The auth tag is embedded in the encrypted payload by AESGCM
        # Extract it (last 16 bytes)
        auth_tag = encrypted_payload[-16:]

        import base64
        return (
            encrypted_payload,
            base64.b64encode(encrypted_dek).decode("ascii"),
            base64.b64encode(nonce).decode("ascii"),
            base64.b64encode(auth_tag).decode("ascii"),
        )

    def _decrypt_payload(
        self,
        encrypted_payload: bytes,
        encrypted_dek_b64: str,
        iv_b64: str,
    ) -> bytes:
        """Decrypt payload using envelope encryption.

        Args:
            encrypted_payload: The encrypted content
            encrypted_dek_b64: Base64-encoded encrypted DEK
            iv_b64: Base64-encoded initialization vector

        Returns:
            Decrypted plaintext
        """
        import base64

        encrypted_dek = base64.b64decode(encrypted_dek_b64)
        iv = base64.b64decode(iv_b64)

        # Decrypt DEK with KMS
        dek = self.kms_client.decrypt(self.kms_key_id, encrypted_dek)

        # Decrypt payload with DEK
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(iv, encrypted_payload, None)

        return plaintext

    def put_bytes(
        self,
        project_id: str,
        payload: bytes,
        *,
        media_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
        retention: RetentionPolicy | None = None,
    ) -> EncryptedArtifactRef:
        """Store an encrypted artifact.

        Args:
            project_id: Project scope
            payload: Artifact content
            media_type: MIME type
            metadata: Additional metadata
            retention: Retention policy (uses default if not specified)

        Returns:
            EncryptedArtifactRef

        Raises:
            ValueError: If payload too large or project_id invalid
            EncryptionError: If encryption fails
        """
        if len(payload) > self.MAX_PAYLOAD_SIZE:
            raise ValueError(
                f"payload exceeds maximum size: {len(payload)} > {self.MAX_PAYLOAD_SIZE}"
            )

        retention = retention or self.default_retention
        digest = sha256_hex(payload)
        target = self._payload_path(project_id, digest)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Check if artifact already exists (idempotent write)
        if target.exists():
            # Return existing ref from metadata sidecar
            metadata_path = self._metadata_path(project_id, digest)
            if metadata_path.exists():
                with metadata_path.open() as f:
                    data = json.load(f)
                return EncryptedArtifactRef(**data["artifact"])

        # Encrypt the payload
        try:
            encrypted_payload, encrypted_dek, iv, auth_tag = self._encrypt_payload(
                payload, retention
            )
        except Exception as e:
            raise EncryptionError(f"encryption failed: {e}") from e

        # Calculate retention expiration
        retention_expires_at = None
        if retention.legal_hold:
            retention_expires_at = None  # Never expires
        else:
            expires = utc_now() + timedelta(days=retention.max_retention_days)
            retention_expires_at = expires.isoformat()

        # Create ref before write attempt (needed for collision handling)
        ref = EncryptedArtifactRef(
            project_id=project_id,
            sha256=digest,
            media_type=media_type,
            size_bytes=len(payload),
            relative_path=str(target.relative_to(self.root)),
            created_at=utc_now().isoformat(),
            encryption_key_id=self.kms_key_id,
            encrypted_dek=encrypted_dek,
            iv=iv,
            auth_tag=auth_tag,
            retention_policy=retention.policy_id,
            retention_expires_at=retention_expires_at,
            legal_hold=retention.legal_hold,
        )

        # Write encrypted content (write-once by hash)
        try:
            with target.open("xb") as handle:
                handle.write(encrypted_payload)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            # File was created by another process - verify content
            existing_encrypted = target.read_bytes()
            try:
                existing_plaintext = self._decrypt_payload(
                    existing_encrypted,
                    ref.encrypted_dek,
                    ref.iv,
                )
                if existing_plaintext != payload:
                    raise EncryptionError(
                        "content-address collision or artifact corruption"
                    )
            except Exception:
                raise EncryptionError(
                    "content-address collision or artifact corruption"
                )

        sidecar = self._metadata_path(project_id, digest)
        if not sidecar.exists():
            from dataclasses import asdict
            sidecar_payload = {
                "artifact": asdict(ref),
                "metadata": metadata or {},
            }
            try:
                with sidecar.open("x", encoding="utf-8") as handle:
                    json.dump(sidecar_payload, handle, sort_keys=True, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:
                pass

        logger.info(
            "encrypted_artifact_stored",
            extra={
                "project_id": project_id,
                "digest": digest,
                "size": len(payload),
                "encrypted_size": len(encrypted_payload),
                "retention_policy": retention.policy_id,
                "legal_hold": retention.legal_hold,
            },
        )

        return ref

    def get_bytes(self, ref: EncryptedArtifactRef) -> bytes:
        """Retrieve and decrypt an artifact.

        Args:
            ref: Artifact reference

        Returns:
            Decrypted plaintext

        Raises:
            ObjectNotFoundError: If artifact not found
            EncryptionError: If decryption fails
        """
        target = self.root / ref.relative_path
        if not target.exists():
            from ..storage.object_store import ObjectNotFoundError
            raise ObjectNotFoundError(f"artifact not found: {ref.relative_path}")

        # Check retention policy
        self._check_retention(ref)

        encrypted_payload = target.read_bytes()

        try:
            plaintext = self._decrypt_payload(
                encrypted_payload,
                ref.encrypted_dek,
                ref.iv,
            )
        except Exception as e:
            raise EncryptionError(f"decryption failed: {e}") from e

        # Verify content hash
        if sha256_hex(plaintext) != ref.sha256:
            raise EncryptionError("content hash mismatch after decryption")

        return plaintext

    def _check_retention(self, ref: EncryptedArtifactRef) -> None:
        """Check if artifact is still under retention.

        Raises:
            RetentionViolationError: If artifact has been deleted or is
                outside retention period
        """
        # Legal hold artifacts never expire
        if ref.legal_hold:
            return

        # Check if past maximum retention
        if ref.retention_expires_at:
            expires = datetime.fromisoformat(ref.retention_expires_at)
            if utc_now() > expires:
                raise RetentionViolationError(
                    f"artifact retention expired: {ref.retention_policy}"
                )

    def verify(self, ref: EncryptedArtifactRef) -> bool:
        """Verify artifact integrity and retention.

        Returns:
            True if artifact exists, decrypts correctly, and is under retention
        """
        try:
            plaintext = self.get_bytes(ref)
            return len(plaintext) == ref.size_bytes and sha256_hex(plaintext) == ref.sha256
        except Exception:
            return False

    def check_retention_compliance(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """Check retention compliance for a project.

        Returns:
            Dict with compliance status and any violations
        """
        project = self._validate_project(project_id)
        project_root = self.root / project

        if not project_root.exists():
            return {"compliant": True, "violations": [], "artifact_count": 0}

        violations = []
        artifact_count = 0

        for metadata_file in project_root.rglob("*.encrypted.json"):
            artifact_count += 1
            try:
                with metadata_file.open() as f:
                    data = json.load(f)
                ref_data = data.get("artifact", {})
                ref = EncryptedArtifactRef(**ref_data)
                self._check_retention(ref)
            except RetentionViolationError as e:
                violations.append({
                    "artifact": str(metadata_file),
                    "error": str(e),
                })
            except Exception as e:
                violations.append({
                    "artifact": str(metadata_file),
                    "error": f"verification failed: {e}",
                })

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "artifact_count": artifact_count,
        }


__all__ = [
    "EncryptedObjectStore",
    "EncryptedArtifactRef",
    "RetentionPolicy",
    "KMSClient",
    "LocalKMSClient",
    "EncryptionError",
    "RetentionViolationError",
    "KeyManagementError",
    "DEFAULT_MIN_RETENTION_DAYS",
    "DEFAULT_MAX_RETENTION_DAYS",
    "LEGAL_HOLD_RETENTION_DAYS",
]
