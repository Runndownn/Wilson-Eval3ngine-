"""Distributed request-rate enforcement for Wilson Eval3ngine.

The security boundary in this module is deliberately stricter than the logging
boundary. Enforcement uses the complete normalized client address (represented
by a one-way token in Redis keys), while logs receive only an anonymized address.
Forwarded client headers are trusted only when the direct peer belongs to an
explicitly configured proxy network.

Production and staging deployments are expected to use Redis. A Redis outage
must not silently turn a multi-instance deployment into independent per-process
rate limiters, so callers can select fail-closed behavior for those environments.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import math
import secrets
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger("wilson.security.rate_limit")


class RateLimitExceeded(Exception):
    """Compatibility exception for callers that choose exception-style handling."""

    def __init__(self, limit: int, window_seconds: int, retry_after: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window_seconds}s. "
            f"Retry after {retry_after}s."
        )


class RateLimitBackendUnavailable(RuntimeError):
    """Raised when the authoritative distributed limiter cannot make a decision."""


class RateLimitConfigurationError(ValueError):
    """Raised when rate-limit trust configuration is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Rate-limit policy for one endpoint family.

    ``burst`` is an explicit number of additional requests permitted inside the
    same sliding window. It is intentionally finite and is not a second,
    unbounded bucket.
    """

    requests_per_minute: int
    burst: int = 0
    per_project: bool = False

    def effective_limit(self) -> int:
        if self.requests_per_minute <= 0:
            raise RateLimitConfigurationError("requests_per_minute must be positive")
        if self.burst < 0:
            raise RateLimitConfigurationError("burst must not be negative")
        return self.requests_per_minute + self.burst


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: int
    limit: int
    key: str
    backend: str


@dataclass(frozen=True, slots=True)
class ClientIdentity:
    """Separate enforcement and privacy representations of one client."""

    address: str
    enforcement_token: str
    log_label: str


_RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]

local min_time = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, min_time)
local current = redis.call('ZCARD', key)

if current < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window))
    return {1, limit - current - 1, math.ceil(window)}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local ttl = window
if #oldest > 0 then
    ttl = math.max(1, math.ceil(window - (now - tonumber(oldest[2]))))
end
return {0, 0, ttl}
"""


class RedisBackend:
    """Redis-backed sliding-window limiter using one atomic Lua operation."""

    def __init__(self, redis_client: Any):
        self._redis = redis_client
        try:
            self._script = self._redis.register_script(_RATE_LIMIT_LUA)
        except Exception as exc:
            raise RateLimitBackendUnavailable(
                "unable to initialize Redis rate-limit script"
            ) from exc

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        now = time.time()
        try:
            result = self._script(
                keys=[key],
                args=[limit, window_seconds, now, secrets.token_hex(16)],
            )
            allowed = int(result[0]) == 1
            remaining = max(0, int(result[1]))
            ttl = max(1, int(result[2]))
        except Exception as exc:
            logger.error(
                "redis_rate_limit_unavailable",
                extra={"error_class": type(exc).__name__},
            )
            raise RateLimitBackendUnavailable(
                "distributed rate-limit backend unavailable"
            ) from exc

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=now + ttl,
            retry_after=ttl if not allowed else 0,
            limit=limit,
            key=key,
            backend="redis",
        )


class InMemoryBackend:
    """Thread-safe sliding-window limiter for development/single-process use."""

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds
        with self._lock:
            timestamps = [t for t in self._windows[key] if t > window_start]
            self._windows[key] = timestamps
            current_count = len(timestamps)

            if current_count < limit:
                timestamps.append(now)
                return RateLimitResult(
                    allowed=True,
                    remaining=max(0, limit - current_count - 1),
                    reset_at=now + window_seconds,
                    retry_after=0,
                    limit=limit,
                    key=key,
                    backend="memory",
                )

            oldest = timestamps[0] if timestamps else now
            retry_after = max(1, math.ceil(window_seconds - (now - oldest)))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=oldest + window_seconds,
                retry_after=retry_after,
                limit=limit,
                key=key,
                backend="memory",
            )


def _parse_networks(values: Iterable[str]) -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for raw in values:
        candidate = raw.strip()
        if not candidate:
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError as exc:
            raise RateLimitConfigurationError(
                f"invalid trusted proxy CIDR: {candidate!r}"
            ) from exc
    return tuple(networks)


def _canonical_ip(value: str) -> str | None:
    try:
        return ipaddress.ip_address(value.strip()).compressed
    except ValueError:
        return None


def anonymize_ip(value: str) -> str:
    """Return a privacy-reduced address label; never use it for enforcement."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "unknown"
    if isinstance(address, ipaddress.IPv4Address):
        return str(ipaddress.ip_network(f"{address}/24", strict=False).network_address)
    return str(ipaddress.ip_network(f"{address}/48", strict=False).network_address)


class ClientIdentityResolver:
    """Resolve an enforcement client without trusting arbitrary forwarding headers."""

    def __init__(self, trusted_proxy_cidrs: Iterable[str] = ()) -> None:
        self._trusted_proxies = _parse_networks(trusted_proxy_cidrs)

    def _is_trusted_proxy(self, address: str) -> bool:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return False
        return any(parsed in network for network in self._trusted_proxies)

    def resolve_address(self, request: Any) -> str:
        direct_raw = request.client.host if getattr(request, "client", None) else "unknown"
        direct = _canonical_ip(direct_raw)
        if direct is None:
            return str(direct_raw)[:128] or "unknown"

        forwarded = request.headers.get("X-Forwarded-For")
        if not forwarded or not self._is_trusted_proxy(direct):
            return direct

        chain: list[str] = []
        for item in forwarded.split(","):
            parsed = _canonical_ip(item)
            if parsed is None:
                logger.warning("malformed_forwarded_for_from_trusted_proxy")
                return direct
            chain.append(parsed)

        for address in reversed(chain):
            if not self._is_trusted_proxy(address):
                return address
        return chain[0] if chain else direct

    def resolve(self, request: Any) -> ClientIdentity:
        address = self.resolve_address(request)
        return ClientIdentity(
            address=address,
            enforcement_token=hashlib.sha256(address.encode("utf-8")).hexdigest(),
            log_label=anonymize_ip(address),
        )


class RateLimiter:
    """Rate limiter with explicit distributed-authority semantics."""

    def __init__(
        self,
        redis_client: Any | None = None,
        default_limit: int = 1000,
        default_window: int = 60,
        *,
        fail_closed: bool = False,
        trusted_proxy_cidrs: Iterable[str] = (),
    ) -> None:
        if default_limit <= 0 or default_window <= 0:
            raise RateLimitConfigurationError(
                "default rate-limit values must be positive"
            )
        self._default_limit = default_limit
        self._default_window = default_window
        self._fail_closed = fail_closed
        self._resolver = ClientIdentityResolver(trusted_proxy_cidrs)

        if redis_client is None:
            if fail_closed:
                raise RateLimitBackendUnavailable(
                    "Redis is required for authoritative distributed rate limiting"
                )
            self._backend: RedisBackend | InMemoryBackend = InMemoryBackend()
            logger.info("rate_limiter_in_memory_backend")
        else:
            try:
                self._backend = RedisBackend(redis_client)
                logger.info("rate_limiter_redis_backend")
            except RateLimitBackendUnavailable:
                if fail_closed:
                    raise
                logger.warning("rate_limiter_redis_init_failed_using_memory")
                self._backend = InMemoryBackend()

    def check(
        self,
        key: str,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        use_limit = limit if limit is not None else self._default_limit
        use_window = window_seconds if window_seconds is not None else self._default_window
        if use_limit <= 0 or use_window <= 0:
            raise RateLimitConfigurationError("rate-limit values must be positive")
        safe_key = self._sanitize_key(key)
        try:
            return self._backend.check_rate_limit(safe_key, use_limit, use_window)
        except RateLimitBackendUnavailable:
            if self._fail_closed:
                raise
            logger.warning("rate_limiter_backend_failed_using_memory_fallback")
            self._backend = InMemoryBackend()
            return self._backend.check_rate_limit(safe_key, use_limit, use_window)

    def resolve_client_identity(self, request: Any) -> ClientIdentity:
        return self._resolver.resolve(request)

    def get_client_ip(self, request: Any) -> str:
        """Compatibility helper returning the exact enforcement address."""
        return self._resolver.resolve_address(request)

    @staticmethod
    def _sanitize_key(key: str) -> str:
        sanitized = "".join(
            c if c.isalnum() or c in ":._-" else "_" for c in key
        )[:256]
        return f"we3:rl:{sanitized}"

    @staticmethod
    def _anonymize_ip(ip: str) -> str:
        return anonymize_ip(ip)


def build_rate_limit_key(
    client_identity: str,
    path: str,
    project_id: str | None = None,
) -> str:
    """Build a bounded rate-limit key.

    The supported pre-authentication middleware intentionally does not supply a
    project ID, because a caller-controlled project header must not create a new
    bucket. Authenticated/internal callers may supply a verified project ID for
    a second, tenant-scoped limiter if required.
    """
    identity_digest = hashlib.sha256(client_identity.encode("utf-8")).hexdigest()[:32]
    path_digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    parts = [f"client:{identity_digest}", f"path:{path_digest}"]
    if project_id:
        project_digest = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]
        # Include the human-readable bounded value only for compatibility and
        # diagnostics; the digest is what prevents oversized/unusual key input.
        safe_project = "".join(
            char if char.isalnum() or char in "_-" else "_"
            for char in project_id
        )[:64]
        parts.extend([f"project:{safe_project}", f"project_sha:{project_digest}"])
    return ":".join(parts)


__all__ = [
    "ClientIdentity",
    "ClientIdentityResolver",
    "InMemoryBackend",
    "RateLimitBackendUnavailable",
    "RateLimitConfig",
    "RateLimitConfigurationError",
    "RateLimitExceeded",
    "RateLimitResult",
    "RateLimiter",
    "RedisBackend",
    "anonymize_ip",
    "build_rate_limit_key",
]
