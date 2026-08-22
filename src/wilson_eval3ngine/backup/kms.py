"""KMS adapters used by backup encryption.

The backup layer consumes the same small envelope-encryption contract as the
encrypted evidence store. AWS KMS is the production-oriented adapter included
here; the existing LocalKMSClient remains available for hermetic tests and
explicitly opted-in development exercises only.
"""

from __future__ import annotations

import os
from typing import Any

from ..storage.encrypted_store import KMSClient, KeyManagementError, LocalKMSClient


class AWSKMSClient:
    """Thin AWS KMS adapter implementing the repository KMSClient protocol."""

    provider_name = "aws-kms"

    def __init__(
        self,
        *,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - optional dependency boundary
            raise KeyManagementError(
                "AWS KMS support requires the 'backup' optional dependency: "
                "python -m pip install -e '.[backup]'"
            ) from exc
        self._client = boto3.client("kms", region_name=region_name)

    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        response = self._client.encrypt(KeyId=key_id, Plaintext=plaintext)
        return bytes(response["CiphertextBlob"])

    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        response = self._client.decrypt(KeyId=key_id, CiphertextBlob=ciphertext)
        return bytes(response["Plaintext"])

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        response = self._client.generate_data_key(KeyId=key_id, KeySpec="AES_256")
        return bytes(response["Plaintext"]), bytes(response["CiphertextBlob"])

    def key_metadata(self, key_id: str) -> dict[str, Any]:
        """Return non-secret KMS identity used in signed backup manifests."""
        response = self._client.describe_key(KeyId=key_id)["KeyMetadata"]
        return {
            "provider": self.provider_name,
            "requested_key_id": key_id,
            "resolved_key_id": str(response.get("KeyId", "")),
            "arn": str(response.get("Arn", "")),
            "key_manager": str(response.get("KeyManager", "")),
            "origin": str(response.get("Origin", "")),
            "multi_region": bool(response.get("MultiRegion", False)),
        }


def kms_identity(kms_client: KMSClient, key_id: str) -> dict[str, Any]:
    """Return a bounded, non-secret identity for any injected KMS implementation."""
    metadata = getattr(kms_client, "key_metadata", None)
    if callable(metadata):
        value = metadata(key_id)
        if isinstance(value, dict):
            return value
    return {
        "provider": getattr(kms_client, "provider_name", type(kms_client).__name__),
        "requested_key_id": key_id,
        "resolved_key_id": key_id,
    }


def build_backup_kms_from_env() -> KMSClient:
    """Build the configured backup KMS client.

    AWS KMS is the default. The local development KMS requires an explicit
    opt-in so a development key is not silently substituted for production key
    custody.
    """
    provider = os.environ.get("WE3_BACKUP_KMS_PROVIDER", "aws").strip().lower()
    if provider == "aws":
        return AWSKMSClient(region_name=os.environ.get("AWS_REGION") or None)
    if provider == "local":
        if os.environ.get("WE3_ALLOW_LOCAL_BACKUP_KMS", "").strip().lower() not in {
            "1",
            "true",
            "yes",
        }:
            raise KeyManagementError(
                "Local backup KMS is disabled. Set WE3_ALLOW_LOCAL_BACKUP_KMS=1 "
                "only for an authorized development/test environment."
            )
        return LocalKMSClient()
    raise KeyManagementError(
        f"Unsupported WE3_BACKUP_KMS_PROVIDER={provider!r}; expected 'aws' or 'local'"
    )


__all__ = [
    "AWSKMSClient",
    "build_backup_kms_from_env",
    "kms_identity",
]
