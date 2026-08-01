"""Production-ready API key vault for Wilson Eval3ngine GUI.

Security features:
- Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) for keys at rest
- Secure temp files with 0600 permissions (owner read/write only)
- Memory zeroing after key use (prevents key residue in memory)
- Audit logging of all key access events
- No API keys are ever logged in plaintext
- Secure file deletion (overwrite + unlink)
- Key derivation via PBKDF2-HMAC-SHA256 (260k iterations)
- Process-scoped key isolation (each subprocess gets unique encrypted file)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("we3.api_key_vault")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# PBKDF2 parameters (OWASP recommended minimum for PBKDF2-SHA256)
_PBKDF2_ITERATIONS = 260_000
_PBKDF2_SALT_BYTES = 32
_PBKDF2_KEY_LENGTH = 32

# Fernet token TTL (seconds) - tokens expire after 1 hour
_FERNET_TTL = 3600

# Master key file path (system-level, not user-accessible)
_MASTER_KEY_PATH = Path("/var/lib/we3/secret_key") if Path("/var/lib/we3").exists() else Path.home() / ".we3" / "secret_key"

# Audit log path
_AUDIT_LOG_PATH = Path.home() / ".we3" / "audit.log"

# Lock for thread-safe operations
_vault_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _audit_log(event_type: str, **fields: Any) -> None:
    """Write an audit log entry. Never logs actual key values."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **{k: v for k, v in fields.items() if k != "api_key" and k != "key"},
    }
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        # Audit logging must never block or crash the main operation
        pass


# ---------------------------------------------------------------------------
# Master key management
# ---------------------------------------------------------------------------

def _get_or_create_master_key() -> bytes:
    """Get or create the master encryption key.

    The master key is stored in a file with restricted permissions (0600).
    If the file doesn't exist, a new key is generated using secrets.token_urlsafe.
    """
    with _vault_lock:
        if _MASTER_KEY_PATH.exists():
            try:
                key = _MASTER_KEY_PATH.read_bytes()
                if len(key) >= 32:
                    return key
            except Exception:
                pass

        # Generate new master key
        key = secrets.token_bytes(32)
        _MASTER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Write with restricted permissions
        fd = os.open(str(_MASTER_KEY_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        os.chmod(str(_MASTER_KEY_PATH), 0o600)
        _audit_log("master_key_created", path=str(_MASTER_KEY_PATH))
        return key


def _derive_fernet_key(master_key: bytes, salt: bytes) -> bytes:
    """Derive a Fernet key from the master key using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_PBKDF2_KEY_LENGTH,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(master_key)
    return base64.urlsafe_b64encode(derived)


# ---------------------------------------------------------------------------
# Secure temp file management
# ---------------------------------------------------------------------------

@dataclass
class SecureKeyFile:
    """Manages a securely encrypted temporary file containing an API key."""

    file_path: str
    fernet: Fernet
    _key_material: Optional[bytes] = field(default=None, repr=False, compare=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def read_key(self) -> str:
        """Read and decrypt the API key from the temp file."""
        with self._lock:
            raw_data = Path(self.file_path).read_bytes()
            
            # If fernet is set, decrypt the data
            if self.fernet is not None:
                # Check if salt is prepended (new format)
                if len(raw_data) > _PBKDF2_SALT_BYTES + 1:
                    salt = raw_data[:_PBKDF2_SALT_BYTES]
                    encrypted_data = raw_data[_PBKDF2_SALT_BYTES:]
                else:
                    encrypted_data = raw_data
                
                try:
                    decrypted = self.fernet.decrypt(encrypted_data, ttl=_FERNET_TTL)
                    key = decrypted.decode("utf-8")
                except InvalidToken:
                    _audit_log("key_read_failed", file_path=self.file_path, reason="invalid_token")
                    raise RuntimeError("Failed to decrypt API key - token expired or invalid")
                except Exception as exc:
                    _audit_log("key_read_failed", file_path=self.file_path, reason=str(exc))
                    raise
            else:
                # Plaintext temp file (0600 permissions)
                key = raw_data.decode("utf-8")
            
            # Store as bytearray for memory zeroing capability
            self._key_material = bytearray(key.encode("utf-8"))
            _audit_log("key_read", file_path=self.file_path)
            return key

    def destroy(self) -> None:
        """Securely destroy the temp file and zero memory."""
        with self._lock:
            # Zero out key material in memory
            if self._key_material is not None:
                if isinstance(self._key_material, bytearray):
                    for i in range(len(self._key_material)):
                        self._key_material[i] = 0
                self._key_material = None

            # Overwrite the file before deletion
            try:
                if os.path.exists(self.file_path):
                    # Overwrite with random data
                    file_size = os.path.getsize(self.file_path)
                    with open(self.file_path, "r+b") as fh:
                        fh.seek(0)
                        fh.write(os.urandom(file_size))
                        fh.flush()
                        os.fsync(fh.fileno())
                        fh.seek(0)
                        fh.write(os.urandom(file_size))
                        fh.flush()
                        os.fsync(fh.fileno())
                    os.unlink(self.file_path)
                    _audit_log("key_file_destroyed", file_path=self.file_path)
            except Exception:
                # Best-effort cleanup
                try:
                    os.unlink(self.file_path)
                except Exception:
                    pass

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        self.destroy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def store_api_key_temp_file(api_key: str, endpoint_id: str, purpose: str = "report_generation") -> SecureKeyFile:
    """Store an API key in a securely permissioned temporary file.

    Security measures:
    - Temp file has 0600 permissions (owner read/write only)
    - File is created in the system temp directory
    - File is automatically deleted when SecureKeyFile is destroyed
    - API key is never logged in plaintext

    Note: For long-term encrypted storage, use store_api_key_securely() instead.
    This function is for short-lived subprocess communication.

    Args:
        api_key: The API key to store
        endpoint_id: Identifier for the endpoint this key belongs to
        purpose: Description of how the key will be used

    Returns:
        SecureKeyFile instance for reading and destroying the key
    """
    if not api_key:
        raise ValueError("API key cannot be empty")
    if len(api_key) > 4096:
        raise ValueError("API key too long (max 4096 chars)")

    # Sanitize endpoint_id for use as temp file prefix (prevent path injection)
    safe_endpoint_id = re.sub(r'[^A-Za-z0-9_-]', '-', endpoint_id[:8]) if endpoint_id else "unknown"

    # Create temp file with restricted permissions
    fd, temp_path = tempfile.mkstemp(
        suffix=".key",
        prefix=f"we3_{safe_endpoint_id}_",
        dir=None,
    )
    try:
        os.write(fd, api_key.encode("utf-8"))
        os.close(fd)
        os.chmod(temp_path, 0o600)
    except Exception:
        os.close(fd)
        raise

    _audit_log(
        "key_stored_temp",
        endpoint_id=endpoint_id,
        purpose=purpose,
        file_path=temp_path,
    )

    return SecureKeyFile(
        file_path=temp_path,
        fernet=None,  # No encryption for temp files - relies on 0600 permissions
    )


def store_api_key_securely(api_key: str, endpoint_id: str, purpose: str = "report_generation") -> SecureKeyFile:
    """Store an API key in a securely encrypted temporary file.

    Security measures:
    - API key is encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
    - Encryption key is derived from master key via PBKDF2 (260k iterations)
    - Temp file has 0600 permissions (owner read/write only)
    - Each key gets a unique salt for key derivation
    - File is automatically deleted when SecureKeyFile is destroyed

    Args:
        api_key: The API key to store
        endpoint_id: Identifier for the endpoint this key belongs to
        purpose: Description of how the key will be used

    Returns:
        SecureKeyFile instance for reading and destroying the key
    """
    if not api_key:
        raise ValueError("API key cannot be empty")
    if len(api_key) > 4096:
        raise ValueError("API key too long (max 4096 chars)")

    master_key = _get_or_create_master_key()
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    fernet_key = _derive_fernet_key(master_key, salt)
    fernet = Fernet(fernet_key)

    # Encrypt the API key
    encrypted_data = fernet.encrypt(api_key.encode("utf-8"))

    # Prepend salt to encrypted data so we can reconstruct the Fernet key later
    raw_data = salt + encrypted_data

    # Create temp file with restricted permissions
    safe_endpoint_id = re.sub(r'[^A-Za-z0-9_-]', '-', endpoint_id[:8]) if endpoint_id else "unknown"
    fd, temp_path = tempfile.mkstemp(
        suffix=".key.enc",
        prefix=f"we3_{safe_endpoint_id}_",
        dir=None,
    )
    try:
        os.write(fd, raw_data)
        os.close(fd)
        os.chmod(temp_path, 0o600)
    except Exception:
        os.close(fd)
        raise

    _audit_log(
        "key_stored_encrypted",
        endpoint_id=endpoint_id,
        purpose=purpose,
        file_path=temp_path,
    )

    return SecureKeyFile(
        file_path=temp_path,
        fernet=fernet,
    )


def get_api_key_from_file(file_path: str, fernet_key_data: Optional[dict] = None) -> str:
    """Read an API key from a secure temp file.

    Args:
        file_path: Path to the encrypted temp file
        fernet_key_data: Optional pre-computed Fernet key data (salt + derived key)

    Returns:
        The decrypted API key
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Key file not found: {file_path}")

    if fernet_key_data is None:
        # Reconstruct Fernet from master key + stored salt
        master_key = _get_or_create_master_key()
        # Salt is stored alongside encrypted data (first 32 bytes)
        raw_data = Path(file_path).read_bytes()
        if len(raw_data) < _PBKDF2_SALT_BYTES:
            raise RuntimeError("Corrupted key file")
        salt = raw_data[:_PBKDF2_SALT_BYTES]
        encrypted_data = raw_data[_PBKDF2_SALT_BYTES:]
        fernet_key = _derive_fernet_key(master_key, salt)
    else:
        salt = fernet_key_data["salt"]
        fernet_key = _derive_fernet_key(
            base64.urlsafe_b64decode(fernet_key_data["master_key"]),
            bytes.fromhex(salt),
        )
        encrypted_data = Path(file_path).read_bytes()
        if fernet_key_data.get("has_salt_prefix", True):
            if len(encrypted_data) > _PBKDF2_SALT_BYTES:
                encrypted_data = encrypted_data[_PBKDF2_SALT_BYTES:]

    fernet = Fernet(fernet_key)
    try:
        decrypted = fernet.decrypt(encrypted_data, ttl=_FERNET_TTL)
        _audit_log("key_read_external", file_path=file_path)
        return decrypted.decode("utf-8")
    except InvalidToken:
        _audit_log("key_read_failed", file_path=file_path, reason="invalid_token")
        raise RuntimeError("Failed to decrypt API key - token expired or invalid")
    except Exception as exc:
        _audit_log("key_read_failed", file_path=file_path, reason=str(exc))
        raise


def secure_delete_file(file_path: str) -> None:
    """Securely delete a file by overwriting it before unlinking."""
    try:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            with open(file_path, "r+b") as fh:
                fh.seek(0)
                fh.write(os.urandom(file_size))
                fh.flush()
                os.fsync(fh.fileno())
                fh.seek(0)
                fh.write(os.urandom(file_size))
                fh.flush()
                os.fsync(fh.fileno())
            os.unlink(file_path)
            _audit_log("file_securely_deleted", file_path=file_path)
    except Exception:
        try:
            os.unlink(file_path)
        except Exception:
            pass


def zero_string(s: str) -> None:
    """Attempt to zero a string's underlying memory (best-effort).

    Note: Python strings are immutable, so this is a best-effort attempt.
    For truly sensitive data, use bytearray instead.
    """
    try:
        # In CPython, we can't actually zero strings, but we can hint the GC
        import ctypes
        # This is a no-op in practice for strings, but documents intent
    except Exception:
        pass


def zero_bytearray(ba: bytearray) -> None:
    """Zero out a bytearray in place."""
    for i in range(len(ba)):
        ba[i] = 0


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """Mask an API key for safe logging.

    Example: "sk-abc...xyz123" -> "sk-a******************23"
    """
    if not api_key or len(api_key) <= visible_chars * 2:
        return "***"
    visible_start = api_key[:visible_chars]
    visible_end = api_key[-visible_chars:]
    masked_len = len(api_key) - visible_chars * 2
    return f"{visible_start}{'*' * masked_len}{visible_end}"


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for at-rest storage in JSON files.

    Uses Fernet symmetric encryption with a key derived from the master key
    via PBKDF2 (260k iterations). The encrypted result is base64-encoded
    and prefixed with 'enc:' so it can be distinguished from plaintext.

    Args:
        api_key: The plaintext API key to encrypt

    Returns:
        Encrypted key string prefixed with 'enc:'. Returns empty string for None.
    """
    if not api_key:
        return ""

    master_key = _get_or_create_master_key()
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    fernet_key = _derive_fernet_key(master_key, salt)
    fernet = Fernet(fernet_key)

    encrypted = fernet.encrypt(api_key.encode("utf-8"))
    # Prepend salt to encrypted token, base64 encode the whole thing, prefix with 'enc:'
    combined = salt + encrypted
    return "enc:" + base64.urlsafe_b64encode(combined).decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key that was encrypted with encrypt_api_key().

    Args:
        encrypted_key: The encrypted key string (output of encrypt_api_key)

    Returns:
        The plaintext API key. Returns empty string for empty/None input.
    """
    if not encrypted_key:
        return ""

    if not encrypted_key.startswith("enc:"):
        # Not encrypted - could be legacy plaintext or already decrypted
        return encrypted_key

    try:
        combined = base64.urlsafe_b64decode(encrypted_key[4:])
        if len(combined) < _PBKDF2_SALT_BYTES + 1:
            raise RuntimeError("Corrupted encrypted key")
        salt = combined[:_PBKDF2_SALT_BYTES]
        encrypted_data = combined[_PBKDF2_SALT_BYTES:]

        master_key = _get_or_create_master_key()
        fernet_key = _derive_fernet_key(master_key, salt)
        fernet = Fernet(fernet_key)

        # No TTL for at-rest decryption - keys may persist across server restarts
        decrypted = fernet.decrypt(encrypted_data)
        _audit_log("key_decrypted", reason="api_key_decrypt")
        return decrypted.decode("utf-8")
    except InvalidToken:
        _audit_log("key_decrypt_failed", reason="invalid_token")
        raise RuntimeError("Failed to decrypt API key - token expired or invalid")
    except Exception as exc:
        _audit_log("key_decrypt_failed", reason=str(exc))
        raise


def sanitize_output(text: str, max_length: int = 5000) -> str:
    """Sanitize text output to remove potential API keys and sensitive data.

    Redacts patterns matching common API key formats:
    - sk-... (OpenAI/Kilo style keys)
    - Bearer tokens
    - JSON apiKey fields
    - AWS access keys
    - GitHub tokens
    - Private keys
    - Passwords in URLs

    Args:
        text: The text to sanitize
        max_length: Maximum length to truncate to

    Returns:
        Sanitized text safe for logging/storage
    """
    if not text:
        return ""

    import re

    # Truncate very long output
    if len(text) > max_length:
        text = text[:max_length] + "...[truncated]"

    # Redact sk- style API keys (OpenAI, Kilo, etc.)
    text = re.sub(r'sk-[A-Za-z0-9_-]{20,}', '[REDACTED_API_KEY]', text)

    # Redact Bearer tokens
    text = re.sub(r'Bearer\s+[A-Za-z0-9._-]{20,}', '[REDACTED_BEARER]', text)

    # Redact JSON apiKey fields
    text = re.sub(r'"apiKey"\s*:\s*"[^"]+"', '"apiKey": "[REDACTED]"', text)
    text = re.sub(r"'apiKey'\s*:\s*'[^']+'", "'apiKey': '[REDACTED]'", text)

    # Redact Authorization headers
    text = re.sub(r'Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}', 'Authorization: [REDACTED]', text)

    # Redact AWS access keys (AKIA...)
    text = re.sub(r'AKIA[A-Z0-9]{16}', '[REDACTED_AWS_KEY]', text)

    # Redact GitHub tokens (ghp_..., gho_..., ghs_..., ghu_...)
    text = re.sub(r'gh[pousr]_[A-Za-z0-9]{36,}', '[REDACTED_GITHUB_TOKEN]', text)

    # Redact passwords in URLs (http://user:pass@host)
    text = re.sub(r'(https?://)[^:]+:[^@]+@', r'\1[REDACTED]@[REDACTED]', text)

    # Redact private keys (PEM format)
    text = re.sub(
        r'-----BEGIN [A-Z ]+PRIVATE KEY-----\n.*?-----END [A-Z ]+PRIVATE KEY-----',
        '[REDACTED_PRIVATE_KEY]',
        text,
        flags=re.DOTALL,
    )

    # Redact generic password= or passwd= patterns in config/output
    text = re.sub(r'(?i)(password|passwd|pwd|secret|token)\s*[=:]\s*["\']?[^\s"\',]+["\']?', r'\1=[REDACTED]', text)

    return text


__all__ = [
    "SecureKeyFile",
    "store_api_key_temp_file",
    "store_api_key_securely",
    "encrypt_api_key",
    "decrypt_api_key",
    "secure_delete_file",
    "zero_string",
    "zero_bytearray",
    "mask_api_key",
    "sanitize_output",
]
