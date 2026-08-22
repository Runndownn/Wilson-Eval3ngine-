"""Streaming envelope encryption for backup payloads.

Backup payloads can be much larger than ordinary evidence artifacts, so this
module deliberately avoids loading an entire physical backup into memory. AES-
256-GCM protects confidentiality and authenticity while the KMS protocol wraps
the one-time data-encryption key (DEK).
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
        return cls(
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


class BackupEncryptionError(RuntimeError):
    """Raised when an encrypted backup payload cannot be trusted or decrypted."""


def _iter_chunks(source: BinaryIO):
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


def encrypt_stream(
    source: BinaryIO,
    destination: Path,
    *,
    kms_client: KMSClient,
    key_id: str,
    kms_identity: dict[str, object],
) -> EncryptionEnvelope:
    """Encrypt a binary stream to ``destination`` using AES-256-GCM."""
    dek, encrypted_dek = kms_client.generate_data_key(key_id)
    if len(dek) != 32:
        raise BackupEncryptionError("KMS returned a DEK that is not 256 bits")

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
                plaintext_digest.update(chunk)
                plaintext_size += len(chunk)
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
        # bytes are immutable, but dropping the reference promptly still limits
        # the plaintext DEK lifetime in application code.
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
    if not verify_ciphertext(source, envelope):
        raise BackupEncryptionError("Encrypted backup payload digest/size mismatch")

    try:
        encrypted_dek = base64.b64decode(envelope.encrypted_dek_base64, validate=True)
        nonce = base64.b64decode(envelope.nonce_base64, validate=True)
        tag = base64.b64decode(envelope.tag_base64, validate=True)
    except Exception as exc:
        raise BackupEncryptionError("Backup encryption metadata is malformed") from exc

    dek = kms_client.decrypt(envelope.key_id, encrypted_dek)
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
                    plaintext.write(clear)
                    plaintext_digest.update(clear)
                    plaintext_size += len(clear)
            final = decryptor.finalize()
            if final:
                plaintext.write(final)
                plaintext_digest.update(final)
                plaintext_size += len(final)
            plaintext.flush()
            os.fsync(plaintext.fileno())
    except Exception as exc:
        destination.unlink(missing_ok=True)
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
    "EncryptionEnvelope",
    "decrypt_file",
    "encrypt_file",
    "encrypt_stream",
    "verify_ciphertext",
]
