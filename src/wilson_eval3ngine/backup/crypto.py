"""Streaming envelope encryption for backup payloads.

Backup payloads can be much larger than ordinary evidence artifacts, so this
module avoids loading an entire physical backup into memory. AES-256-GCM
protects confidentiality and authenticity while the KMS protocol wraps the
one-time data-encryption key (DEK).

This implementation intentionally caps a single GCM message. GCM has a finite
per-IV invocation bound; silently streaming arbitrarily large database backups
through one nonce would create a cryptographic correctness hazard. Deployments
that need objects above this conservative bound must use a chunked/object-store
backup service rather than bypassing the guard.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..storage.encrypted_store import KMSClient


CHUNK_SIZE = 1024 * 1024
# NIST SP 800-38D limits GCM plaintext length for one invocation to less than
# 2^39-256 bits. Stay one full application chunk below that theoretical ceiling
# so the guard is simple and conservative.
MAX_GCM_PLAINTEXT_BYTES = (1 << 36) - CHUNK_SIZE


@dataclass(frozen=True, slots=True)
class EncryptionEnvelope:
    """Metadata required to verify and decrypt one encrypted backup object."""

    algorithm: str
    key_id: str
    kms_identity: dict[str, object]
    encrypted_dek_base64: str
    nonce_base64: str
    tag_base64: str
    plaintext_sha256: str
    ciphertext_sha256: str
    plaintext_size_bytes: int
    ciphertext_size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "EncryptionEnvelope":
        envelope = cls(
            algorithm=str(value["algorithm"]),
            key_id=str(value["key_id"]),
            kms_identity=dict(value.get("kms_identity") or {}),
            encrypted_dek_base64=str(value["encrypted_dek_base64"]),
            nonce_base64=str(value["nonce_base64"]),
            tag_base64=str(value["tag_base64"]),
            plaintext_sha256=str(value["plaintext_sha256"]),
            ciphertext_sha256=str(value["ciphertext_sha256"]),
            plaintext_size_bytes=int(value["plaintext_size_bytes"]),
            ciphertext_size_bytes=int(value["ciphertext_size_bytes"]),
        )
        if envelope.plaintext_size_bytes < 0 or envelope.ciphertext_size_bytes < 0:
            raise BackupEncryptionError("Backup encryption sizes must be non-negative")
        if envelope.plaintext_size_bytes > MAX_GCM_PLAINTEXT_BYTES:
            raise BackupEncryptionError(
                "Backup payload exceeds the supported single-message AES-GCM bound"
            )
        return envelope


class BackupEncryptionError(RuntimeError):
    """Raised when an encrypted backup payload cannot be trusted or decrypted."""


def _iter_chunks(source: BinaryIO):
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


def _operation_key_id(
    requested_key_id: str,
    identity: dict[str, object],
) -> str:
    """Prefer immutable KMS identity while retaining requested key provenance."""
    for field in ("arn", "resolved_key_id"):
        value = identity.get(field)
        if value:
            return str(value)
    return requested_key_id


def _decode_metadata(value: str, *, field_name: str, expected_length: int | None = None) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise BackupEncryptionError(
            f"Backup encryption metadata field {field_name!r} is malformed"
        ) from exc
    if expected_length is not None and len(decoded) != expected_length:
        raise BackupEncryptionError(
            f"Backup encryption metadata field {field_name!r} has an invalid length"
        )
    return decoded


def encrypt_stream(
    source: BinaryIO,
    destination: Path,
    *,
    kms_client: KMSClient,
    key_id: str,
    kms_identity: dict[str, object],
) -> EncryptionEnvelope:
    """Encrypt a binary stream to ``destination`` using one bounded AES-256-GCM message."""
    operation_key_id = _operation_key_id(key_id, kms_identity)
    dek, encrypted_dek = kms_client.generate_data_key(operation_key_id)
    if len(dek) != 32:
        raise BackupEncryptionError("KMS returned a DEK that is not 256 bits")
    if not encrypted_dek:
        raise BackupEncryptionError("KMS returned an empty wrapped DEK")

    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()
    plaintext_digest = hashlib.sha256()
    ciphertext_digest = hashlib.sha256()
    plaintext_size = 0
    ciphertext_size = 0

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as target:
            for chunk in _iter_chunks(source):
                plaintext_size += len(chunk)
                if plaintext_size > MAX_GCM_PLAINTEXT_BYTES:
                    raise BackupEncryptionError(
                        "Backup payload exceeds the supported single-message AES-GCM bound"
                    )
                plaintext_digest.update(chunk)
                encrypted = encryptor.update(chunk)
                if encrypted:
                    target.write(encrypted)
                    ciphertext_digest.update(encrypted)
                    ciphertext_size += len(encrypted)
            final = encryptor.finalize()
            if final:
                target.write(final)
                ciphertext_digest.update(final)
                ciphertext_size += len(final)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        # Python immutable bytes cannot be reliably zeroized in place. Drop the
        # explicit reference promptly without claiming memory erasure guarantees.
        dek = b""

    return EncryptionEnvelope(
        algorithm="AES-256-GCM",
        key_id=key_id,
        kms_identity=dict(kms_identity),
        encrypted_dek_base64=base64.b64encode(encrypted_dek).decode("ascii"),
        nonce_base64=base64.b64encode(nonce).decode("ascii"),
        tag_base64=base64.b64encode(encryptor.tag).decode("ascii"),
        plaintext_sha256=plaintext_digest.hexdigest(),
        ciphertext_sha256=ciphertext_digest.hexdigest(),
        plaintext_size_bytes=plaintext_size,
        ciphertext_size_bytes=ciphertext_size,
    )


def encrypt_file(
    source: Path,
    destination: Path,
    *,
    kms_client: KMSClient,
    key_id: str,
    kms_identity: dict[str, object],
) -> EncryptionEnvelope:
    with source.open("rb") as handle:
        return encrypt_stream(
            handle,
            destination,
            kms_client=kms_client,
            key_id=key_id,
            kms_identity=kms_identity,
        )


def verify_ciphertext(path: Path, envelope: EncryptionEnvelope) -> bool:
    """Verify the immutable ciphertext identity without decrypting it."""
    if envelope.ciphertext_size_bytes < 0:
        return False
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for chunk in _iter_chunks(handle):
                digest.update(chunk)
                size += len(chunk)
    except OSError:
        return False
    return (
        size == envelope.ciphertext_size_bytes
        and digest.hexdigest() == envelope.ciphertext_sha256
    )


def decrypt_file(
    source: Path,
    destination: Path,
    *,
    kms_client: KMSClient,
    envelope: EncryptionEnvelope,
) -> None:
    """Decrypt and authenticate one backup object, then verify plaintext hash."""
    if envelope.algorithm != "AES-256-GCM":
        raise BackupEncryptionError(
            f"Unsupported backup encryption algorithm: {envelope.algorithm}"
        )
    if envelope.plaintext_size_bytes > MAX_GCM_PLAINTEXT_BYTES:
        raise BackupEncryptionError(
            "Backup payload exceeds the supported single-message AES-GCM bound"
        )
    if not verify_ciphertext(source, envelope):
        raise BackupEncryptionError("Encrypted backup payload digest/size mismatch")

    encrypted_dek = _decode_metadata(
        envelope.encrypted_dek_base64,
        field_name="encrypted_dek_base64",
    )
    if not encrypted_dek:
        raise BackupEncryptionError("Backup encryption metadata contains an empty wrapped DEK")
    nonce = _decode_metadata(
        envelope.nonce_base64,
        field_name="nonce_base64",
        expected_length=12,
    )
    tag = _decode_metadata(
        envelope.tag_base64,
        field_name="tag_base64",
        expected_length=16,
    )

    operation_key_id = _operation_key_id(envelope.key_id, envelope.kms_identity)
    dek = kms_client.decrypt(operation_key_id, encrypted_dek)
    if len(dek) != 32:
        raise BackupEncryptionError("KMS unwrapped a DEK that is not 256 bits")

    decryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce, tag)).decryptor()
    plaintext_digest = hashlib.sha256()
    plaintext_size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as encrypted, destination.open("xb") as plaintext:
            for chunk in _iter_chunks(encrypted):
                clear = decryptor.update(chunk)
                if clear:
                    plaintext_size += len(clear)
                    if plaintext_size > MAX_GCM_PLAINTEXT_BYTES:
                        raise BackupEncryptionError(
                            "Decrypted backup exceeds the supported AES-GCM bound"
                        )
                    plaintext.write(clear)
                    plaintext_digest.update(clear)
            final = decryptor.finalize()
            if final:
                plaintext_size += len(final)
                if plaintext_size > MAX_GCM_PLAINTEXT_BYTES:
                    raise BackupEncryptionError(
                        "Decrypted backup exceeds the supported AES-GCM bound"
                    )
                plaintext.write(final)
                plaintext_digest.update(final)
            plaintext.flush()
            os.fsync(plaintext.fileno())
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, BackupEncryptionError):
            raise
        raise BackupEncryptionError("Backup payload decryption/authentication failed") from exc
    finally:
        dek = b""

    if (
        plaintext_size != envelope.plaintext_size_bytes
        or plaintext_digest.hexdigest() != envelope.plaintext_sha256
    ):
        destination.unlink(missing_ok=True)
        raise BackupEncryptionError("Decrypted backup payload digest/size mismatch")


__all__ = [
    "BackupEncryptionError",
    "CHUNK_SIZE",
    "EncryptionEnvelope",
    "MAX_GCM_PLAINTEXT_BYTES",
    "decrypt_file",
    "encrypt_file",
    "encrypt_stream",
    "verify_ciphertext",
]
