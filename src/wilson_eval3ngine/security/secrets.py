"""Development Fernet compatibility utilities.

This module predates the production secret-authority contract in
``security.secrets_backend``.  It remains useful for deterministic local tests
and migration of older encrypted local state, but it is deliberately rejected
in staging/production.  Production code must obtain secret material from an
external authority/KMS boundary rather than generate, persist, or replicate raw
keys through this helper.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken  # type: ignore[import-untyped]

logger = logging.getLogger("wilson.security.secrets")


class SecretValidationError(Exception):
    """Raised when local development key material fails validation."""


@dataclass(frozen=True, slots=True)
class SecretMetadata:
    key_id: str
    algorithm: str
    created_at: float
    expires_at: float | None = None
    rotation_interval_seconds: int = 86400 * 30
    description: str = ""


@dataclass
class KeyRotationResult:
    old_key_id: str
    new_key_id: str
    rotated_at: float
    entries_migrated: int
    errors: list[str] = field(default_factory=list)


class SecretsManager:
    """Local Fernet keyring for development/test compatibility only.

    Raw keys stay in process memory and, when explicitly requested for a local
    development key file, in that mode-0600 file. Redis receives metadata only;
    it is never used as a plaintext key-distribution channel.
    """

    def __init__(
        self,
        key_file_path: str | None = None,
        env_var_name: str = "WE3_ENCRYPTION_KEY",
        redis_client: Any | None = None,
        *,
        environment: str | None = None,
        allow_generate_dev_key: bool = True,
    ) -> None:
        self._environment = (
            environment or os.environ.get("WE3_ENVIRONMENT", "development")
        ).strip().lower()
        if self._environment in {"staging", "production"}:
            raise SecretValidationError(
                "SecretsManager is development-only; use the external secret/KMS authority"
            )

        self._env_var_name = env_var_name
        self._key_file_path = key_file_path
        self._redis = redis_client
        self._allow_generate_dev_key = allow_generate_dev_key
        self._keyring: dict[str, Fernet] = {}
        self._raw_keys: dict[str, str] = {}
        self._metadata: dict[str, SecretMetadata] = {}
        self._current_key_id: str | None = None
        self._load_keys()

    @staticmethod
    def _validate_fernet_key(key: str) -> Fernet:
        try:
            return Fernet(key.encode("ascii"))
        except Exception as exc:
            raise SecretValidationError("invalid Fernet key material") from exc

    def _register_key(self, key: str, *, description: str) -> str:
        fernet = self._validate_fernet_key(key)
        key_id = self._derive_key_id(key)
        if key_id not in self._keyring:
            self._keyring[key_id] = fernet
            self._raw_keys[key_id] = key
            self._metadata[key_id] = SecretMetadata(
                key_id=key_id,
                algorithm="fernet",
                created_at=time.time(),
                description=description,
            )
        if self._current_key_id is None:
            self._current_key_id = key_id
        return key_id

    def _load_keys(self) -> None:
        env_key = os.environ.get(self._env_var_name)
        if env_key:
            key_id = self._register_key(
                env_key.strip(),
                description="environment-provided development key",
            )
            logger.info("local_secret_key_loaded", extra={"key_id": key_id})

        if self._key_file_path:
            key_path = Path(self._key_file_path)
            if key_path.exists():
                metadata = key_path.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                    raise SecretValidationError(
                        "development key file must be a regular non-symlink file"
                    )
                if stat.S_IMODE(metadata.st_mode) & 0o077:
                    raise SecretValidationError(
                        "development key file permissions are too broad"
                    )
                if metadata.st_size <= 0 or metadata.st_size > 64 * 1024:
                    raise SecretValidationError(
                        "development key file size is invalid"
                    )
                try:
                    lines = key_path.read_text(encoding="ascii").splitlines()
                except OSError as exc:
                    raise SecretValidationError(
                        "development key file could not be read"
                    ) from exc
                for index, line in enumerate(lines, start=1):
                    value = line.strip()
                    if value:
                        self._register_key(
                            value,
                            description=f"development key file line {index}",
                        )

        if not self._keyring:
            if not self._allow_generate_dev_key:
                raise SecretValidationError("no local development key is configured")
            self._generate_dev_key()

        if self._current_key_id is None:
            self._current_key_id = next(iter(self._keyring))

    def _generate_dev_key(self) -> str:
        logger.warning("no_local_key_configured_generating_development_key")
        key = Fernet.generate_key().decode("ascii")
        key_id = self._register_key(key, description="auto-generated development key")
        self._current_key_id = key_id
        if self._key_file_path:
            self._write_key_file()
        return key_id

    @staticmethod
    def _derive_key_id(key: str) -> str:
        return hashlib.sha256(key.encode("ascii")).hexdigest()[:16]

    def get_current_key_id(self) -> str | None:
        return self._current_key_id

    def get_fernet(self, key_id: str | None = None) -> Fernet:
        selected = key_id or self._current_key_id
        if selected is None or selected not in self._keyring:
            raise SecretValidationError("requested key is unavailable")
        return self._keyring[selected]

    def encrypt(
        self,
        plaintext: bytes,
        key_id: str | None = None,
    ) -> tuple[bytes, str]:
        selected = key_id or self._current_key_id
        if selected is None:
            raise SecretValidationError("no current key is available")
        return self.get_fernet(selected).encrypt(plaintext), selected

    def decrypt(self, encrypted_data: bytes, key_id: str | None = None) -> bytes:
        if key_id is not None:
            try:
                return self.get_fernet(key_id).decrypt(encrypted_data)
            except InvalidToken as exc:
                raise SecretValidationError("decryption failed with selected key") from exc

        for fernet in self._keyring.values():
            try:
                return fernet.decrypt(encrypted_data)
            except InvalidToken:
                continue
        raise SecretValidationError("decryption failed with available keys")

    def rotate_key(self, new_key: str | None = None) -> KeyRotationResult:
        old_key_id = self._current_key_id
        value = new_key or Fernet.generate_key().decode("ascii")
        new_key_id = self._derive_key_id(value)
        if new_key_id in self._keyring:
            raise SecretValidationError("rotation key is already present")

        self._register_key(value, description="rotated development key")
        self._current_key_id = new_key_id
        if self._key_file_path:
            self._write_key_file()
        self._publish_metadata(new_key_id)

        logger.info(
            "local_key_rotated",
            extra={"old_key_id": old_key_id, "new_key_id": new_key_id},
        )
        return KeyRotationResult(
            old_key_id=old_key_id or "none",
            new_key_id=new_key_id,
            rotated_at=time.time(),
            entries_migrated=0,
            errors=[],
        )

    def _write_key_file(self) -> None:
        """Atomically persist the explicit local development keyring."""
        if not self._key_file_path:
            return
        key_path = Path(self._key_file_path)
        key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        ordered_ids = []
        if self._current_key_id:
            ordered_ids.append(self._current_key_id)
        ordered_ids.extend(
            key_id for key_id in self._raw_keys if key_id != self._current_key_id
        )
        payload = "\n".join(self._raw_keys[key_id] for key_id in ordered_ids) + "\n"

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{key_path.name}.",
            dir=key_path.parent,
            text=True,
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="ascii", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, key_path)
            key_path.chmod(0o600)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

    def _publish_metadata(self, key_id: str) -> None:
        """Publish non-secret rotation metadata only; never raw key bytes."""
        if self._redis is None:
            return
        metadata = self._metadata[key_id]
        payload = json.dumps(
            {
                "key_id": metadata.key_id,
                "algorithm": metadata.algorithm,
                "created_at": metadata.created_at,
                "rotation_interval_seconds": metadata.rotation_interval_seconds,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            self._redis.set(
                f"we3:secret-metadata:{key_id}",
                payload,
                ex=metadata.rotation_interval_seconds * 2,
            )
        except Exception as exc:
            logger.warning(
                "local_key_metadata_publish_failed",
                extra={"error_class": type(exc).__name__},
            )

    def get_key_metadata(self, key_id: str) -> SecretMetadata | None:
        return self._metadata.get(key_id)

    def list_keys(self) -> list[SecretMetadata]:
        return list(self._metadata.values())

    def needs_rotation(self, key_id: str | None = None) -> bool:
        selected = key_id or self._current_key_id
        if selected is None or selected not in self._metadata:
            return True
        metadata = self._metadata[selected]
        if metadata.expires_at is not None:
            return time.time() > metadata.expires_at
        return time.time() - metadata.created_at > metadata.rotation_interval_seconds

    def health_check(self) -> dict[str, Any]:
        keys_needing_rotation = [
            key_id for key_id in self._metadata if self.needs_rotation(key_id)
        ]
        return {
            "status": "ok" if self._keyring else "error",
            "key_count": len(self._keyring),
            "current_key_id": self._current_key_id,
            "keys_needing_rotation": keys_needing_rotation,
            "errors": [] if self._keyring else ["No keys loaded"],
            "scope": "development_only",
        }

    def validate_key(self, key: str) -> bool:
        try:
            Fernet(key.encode("ascii"))
            return True
        except Exception:
            return False


def load_secret_from_env(
    env_var: str,
    required: bool = False,
    default: str | None = None,
) -> str | None:
    """Load a development secret without logging its value."""
    value = os.environ.get(env_var)
    if not value:
        if required:
            raise SecretValidationError("required development secret is not configured")
        return default
    if len(value) < 8:
        logger.warning("development_secret_short", extra={"env_var": env_var})
    return value


def validate_for_production(secrets_manager: SecretsManager) -> list[str]:
    del secrets_manager
    return [
        "SecretsManager is development-only; production must use SecretBackend/KMS custody"
    ]


__all__ = [
    "SecretValidationError",
    "SecretMetadata",
    "KeyRotationResult",
    "SecretsManager",
    "load_secret_from_env",
    "validate_for_production",
]
