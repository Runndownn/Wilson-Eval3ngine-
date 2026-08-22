"""Pluggable secret authority with explicit development/production boundaries.

Public code owns the contract and validation. Real production secret values,
endpoints, namespaces, identities, and vendor-specific plugins remain private
deployment inputs.
"""

from __future__ import annotations

import importlib
import os
import re
import stat
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

_SECRET_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_MAX_SECRET_BYTES = 64 * 1024


class SecretBackendError(RuntimeError):
    """Safe secret-backend failure without secret material."""


@runtime_checkable
class SecretBackend(Protocol):
    backend_id: str
    external_authority: bool

    def read(self, name: str) -> bytes: ...
    def healthcheck(self) -> bool: ...


@dataclass(slots=True)
class SecretLease(AbstractContextManager["SecretLease"]):
    """Bounded mutable secret buffer with deterministic zeroing."""

    name: str
    backend_id: str
    _value: bytearray = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def obtain(cls, backend: SecretBackend, name: str) -> "SecretLease":
        validated = validate_secret_name(name)
        value = backend.read(validated)
        if not isinstance(value, bytes):
            raise SecretBackendError("secret backend returned a non-bytes value")
        if not value or len(value) > _MAX_SECRET_BYTES:
            raise SecretBackendError("secret value is empty or exceeds the size limit")
        return cls(validated, backend.backend_id, bytearray(value))

    def bytes(self) -> bytes:
        with self._lock:
            if self._closed:
                raise SecretBackendError("secret lease is closed")
            return bytes(self._value)

    def text(self, encoding: str = "utf-8") -> str:
        return self.bytes().decode(encoding)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            for index in range(len(self._value)):
                self._value[index] = 0
            self._closed = True

    def __exit__(self, *_exc: object) -> None:
        self.close()


def validate_secret_name(name: str) -> str:
    if not _SECRET_NAME.fullmatch(name):
        raise ValueError("secret names must match [A-Z][A-Z0-9_]{0,127}")
    return name


@dataclass(frozen=True, slots=True)
class EnvironmentSecretBackend:
    """Development/test backend; never a production secret authority."""

    prefix: str = "WE3_SECRET_"
    backend_id: str = "environment"
    external_authority: bool = False

    def read(self, name: str) -> bytes:
        value = os.environ.get(self.prefix + validate_secret_name(name))
        if value is None:
            raise SecretBackendError("required secret is unavailable")
        return value.encode("utf-8")

    def healthcheck(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class MountedSecretBackend:
    """Read-only secret files injected by an external orchestrator.

    Reads are descriptor-based. ``O_NOFOLLOW`` prevents the final path component
    from becoming a symlink between validation and use, and ``fstat`` validates
    the object that was actually opened. Files must be regular, owned by the
    current service identity (or root), owner-readable, and inaccessible to
    group/other users.
    """

    root: Path
    backend_id: str = "mounted"
    external_authority: bool = True

    def __post_init__(self) -> None:
        raw_root = Path(self.root)
        try:
            metadata = raw_root.lstat()
        except OSError as exc:
            raise SecretBackendError("mounted secret root is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise SecretBackendError("mounted secret root must not be a symlink")
        resolved = raw_root.resolve(strict=True)
        if not resolved.is_dir():
            raise SecretBackendError("mounted secret root is not a directory")
        object.__setattr__(self, "root", resolved)

    def _path(self, name: str) -> Path:
        candidate = self.root / validate_secret_name(name)
        if candidate.parent != self.root:
            raise SecretBackendError("secret path escaped the configured root")
        return candidate

    @staticmethod
    def _validate_open_file(metadata: os.stat_result) -> None:
        if not stat.S_ISREG(metadata.st_mode):
            raise SecretBackendError("secret must be a regular file")
        permissions = stat.S_IMODE(metadata.st_mode)
        if permissions & 0o077:
            raise SecretBackendError("secret file permissions are too broad")
        if not permissions & stat.S_IRUSR:
            raise SecretBackendError("secret file is not owner-readable")
        if metadata.st_size <= 0 or metadata.st_size > _MAX_SECRET_BYTES:
            raise SecretBackendError("secret file is empty or exceeds the size limit")
        current_uid = os.geteuid() if hasattr(os, "geteuid") else None
        if current_uid is not None and metadata.st_uid not in {0, current_uid}:
            raise SecretBackendError("secret file owner is not trusted")

    def read(self, name: str) -> bytes:
        path = self._path(name)
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise SecretBackendError("secret file could not be opened safely") from exc

        try:
            metadata = os.fstat(descriptor)
            self._validate_open_file(metadata)
            chunks: list[bytes] = []
            remaining = _MAX_SECRET_BYTES + 1
            while remaining > 0:
                chunk = os.read(descriptor, min(8192, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            value = b"".join(chunks)
        finally:
            os.close(descriptor)

        if len(value) > _MAX_SECRET_BYTES:
            raise SecretBackendError("secret exceeds the size limit")
        value = value.rstrip(b"\r\n")
        if not value:
            raise SecretBackendError("secret value is empty")
        return value

    def healthcheck(self) -> bool:
        return self.root.is_dir() and os.access(self.root, os.R_OK | os.X_OK)


def _load_plugin(spec: str, configuration: Mapping[str, str]) -> SecretBackend:
    module_name, separator, factory_name = spec.partition(":")
    if not separator or not module_name or not factory_name:
        raise SecretBackendError("plugin must use module:factory syntax")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
        backend = factory(dict(configuration))
    except Exception as exc:
        raise SecretBackendError("external secret backend could not be initialized") from exc
    if not isinstance(backend, SecretBackend):
        raise SecretBackendError("external factory did not return a SecretBackend")
    if not backend.external_authority:
        raise SecretBackendError("production plugin must declare external authority")
    return backend


def build_secret_backend(
    *,
    environment: str,
    mode: str | None = None,
    plugin: str | None = None,
    mounted_root: str | Path | None = None,
    configuration: Mapping[str, str] | None = None,
) -> SecretBackend:
    selected = (
        mode or os.environ.get("WE3_SECRET_BACKEND", "environment")
    ).strip().lower()
    configuration = configuration or {}
    if selected == "environment":
        backend: SecretBackend = EnvironmentSecretBackend()
    elif selected == "mounted":
        root = mounted_root or os.environ.get("WE3_SECRET_MOUNT")
        if not root:
            raise SecretBackendError("mounted backend requires a configured root")
        backend = MountedSecretBackend(Path(root))
    elif selected == "plugin":
        spec = plugin or os.environ.get("WE3_SECRET_PLUGIN", "")
        if not spec:
            raise SecretBackendError("plugin backend requires WE3_SECRET_PLUGIN")
        backend = _load_plugin(spec, configuration)
    else:
        raise SecretBackendError("unknown secret backend mode")

    if environment in {"production", "staging"} and not backend.external_authority:
        raise SecretBackendError("production requires an external secret authority")
    if not backend.healthcheck():
        raise SecretBackendError("secret authority healthcheck failed")
    return backend


__all__ = [
    "EnvironmentSecretBackend",
    "MountedSecretBackend",
    "SecretBackend",
    "SecretBackendError",
    "SecretLease",
    "build_secret_backend",
    "validate_secret_name",
]
