"""Bounded Redis adapter for security-critical shared state.

Redis is used as an authority for token revocation and distributed request-rate
state in staging/production. Raw client exceptions are implementation details;
this adapter converts them to one stable RuntimeError subclass without logging
keys, values, connection strings, or backend messages. Callers then choose their
own safe HTTP/error contract while preserving fail-closed behavior.
"""

from __future__ import annotations

from typing import Any, Callable


class SecurityStateUnavailable(RuntimeError):
    """The shared Redis security-state authority cannot make a decision."""


class RedisSecurityAuthority:
    """Narrow exception-normalizing facade over the Redis methods WE3 uses."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _raise(exc: Exception) -> None:
        raise SecurityStateUnavailable(
            "shared security-state authority is unavailable"
        ) from exc

    def ping(self) -> Any:
        try:
            return self._client.ping()
        except Exception as exc:
            self._raise(exc)

    def exists(self, key: str) -> Any:
        try:
            return self._client.exists(key)
        except Exception as exc:
            self._raise(exc)

    def setex(self, key: str, ttl: int, value: str) -> Any:
        try:
            return self._client.setex(key, ttl, value)
        except Exception as exc:
            self._raise(exc)

    def get(self, key: str) -> Any:
        try:
            return self._client.get(key)
        except Exception as exc:
            self._raise(exc)

    def set(self, key: str, value: Any, **kwargs: Any) -> Any:
        try:
            return self._client.set(key, value, **kwargs)
        except Exception as exc:
            self._raise(exc)

    def register_script(self, script: str) -> Callable[..., Any]:
        try:
            registered = self._client.register_script(script)
        except Exception as exc:
            self._raise(exc)

        def invoke(*args: Any, **kwargs: Any) -> Any:
            try:
                return registered(*args, **kwargs)
            except Exception as exc:
                self._raise(exc)

        return invoke


__all__ = ["RedisSecurityAuthority", "SecurityStateUnavailable"]
