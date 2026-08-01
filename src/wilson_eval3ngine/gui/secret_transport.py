"""Ephemeral secret handoff for report-generation child processes.

The report generator historically consumed an owner-only regular file.  That
protected the value from other users but still left plaintext key material on
the filesystem.  This module preserves the existing narrow ``file_path``
contract while replacing the regular file with a one-shot POSIX FIFO held in a
private temporary directory.

The secret exists only in the parent process and the kernel pipe buffer.  A
single reader receives it and EOF, after which the bytearray is overwritten and
the FIFO directory is removed.  Platforms without ``os.mkfifo`` fail closed;
they must use a future native secure transport rather than silently falling
back to plaintext storage.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_MAX_SECRET_BYTES = 4096


def _zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


@dataclass
class OneShotSecretPipe:
    """A compatible one-shot secret handle backed by a named pipe."""

    file_path: str
    _directory: Path = field(repr=False)
    _secret: bytearray = field(repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _closed: bool = field(default=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _error: BaseException | None = field(default=None, repr=False)

    @classmethod
    def create(cls, api_key: str, endpoint_id: str) -> "OneShotSecretPipe":
        if not hasattr(os, "mkfifo"):
            raise RuntimeError("Secure report credential transport requires POSIX FIFO support")
        encoded = api_key.encode("utf-8")
        if not encoded:
            raise ValueError("API key cannot be empty")
        if len(encoded) > _MAX_SECRET_BYTES:
            raise ValueError(f"API key exceeds {_MAX_SECRET_BYTES} bytes")

        safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", endpoint_id or "unknown")[:24]
        directory = Path(tempfile.mkdtemp(prefix=f"we3-{safe_id}-secret-"))
        os.chmod(directory, 0o700)
        fifo = directory / "credential.pipe"
        os.mkfifo(fifo, 0o600)

        handle = cls(str(fifo), directory, bytearray(encoded))
        handle._thread = threading.Thread(
            target=handle._write_once,
            name=f"we3-secret-{safe_id}",
            daemon=True,
        )
        handle._thread.start()
        return handle

    def _write_once(self) -> None:
        try:
            descriptor = os.open(self.file_path, os.O_WRONLY)
            try:
                view = memoryview(self._secret)
                written = 0
                while written < len(view):
                    written += os.write(descriptor, view[written:])
            finally:
                os.close(descriptor)
        except BaseException as exc:  # recorded for deterministic cleanup/tests
            self._error = exc
        finally:
            _zero(self._secret)

    def read_key(self) -> str:
        """Read the one-shot value for compatibility and tests."""

        with open(self.file_path, "rb", buffering=0) as handle:
            value = handle.read(_MAX_SECRET_BYTES + 1)
        if len(value) > _MAX_SECRET_BYTES:
            raise RuntimeError("Secret transport exceeded its size limit")
        return value.decode("utf-8")

    def destroy(self) -> None:
        """Unblock any pending writer, erase memory, and remove all paths."""

        with self._lock:
            if self._closed:
                return
            self._closed = True

            thread = self._thread
            if thread and thread.is_alive() and os.path.exists(self.file_path):
                try:
                    # Opening a non-blocking reader releases a writer waiting
                    # for a child that never started or never consumed the key.
                    descriptor = os.open(self.file_path, os.O_RDONLY | os.O_NONBLOCK)
                    os.close(descriptor)
                except OSError:
                    pass
                thread.join(timeout=1.0)

            _zero(self._secret)
            try:
                Path(self.file_path).unlink(missing_ok=True)
            finally:
                shutil.rmtree(self._directory, ignore_errors=True)

    def __enter__(self) -> "OneShotSecretPipe":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.destroy()

    def __del__(self) -> None:  # pragma: no cover - best-effort process cleanup
        try:
            self.destroy()
        except Exception:
            pass


def store_api_key_pipe(
    api_key: str,
    endpoint_id: str,
    purpose: str = "report_generation",
) -> OneShotSecretPipe:
    """Create a one-shot FIFO while retaining the legacy call signature."""

    del purpose
    return OneShotSecretPipe.create(api_key, endpoint_id)


__all__ = ["OneShotSecretPipe", "store_api_key_pipe"]
