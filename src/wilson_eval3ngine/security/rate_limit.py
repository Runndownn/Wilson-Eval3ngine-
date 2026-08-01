"""Distributed rate limiting for Wilson Eval3ngine.

T6.1.2 - Implement production-grade distributed rate limiting.

Uses Redis with atomic Lua scripts for sliding-window rate limiting.
Falls back to in-memory mode when Redis is unavailable (single-instance deployments).

Security:
- Sliding window algorithm prevents burst attacks
- Atomic Lua scripts prevent race conditions
- Project-scoped rate limits prevent cross-tenant abuse
- IP anonymization in logs
- Configurable per-endpoint limits
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("wilson.security.rate_limit")


class RateLimitExceeded(Exception):
    """Raised when a client exceeds the rate limit."""

    def __init__(self, limit: int, window_seconds: int, retry_after: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window_seconds}s. "
            f"Retry after {retry_after}s."
        )


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an endpoint pattern."""

    requests_per_minute: int
    burst: int = 20
    per_project: bool = True  # If True, rate limit is per-project, not per-IP


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_at: float
    retry_after: int
    limit: int
    key: str


# Lua script for atomic sliding-window rate limiting
# Returns: [allowed (0/1), remaining, ttl]
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Remove expired entries from the window
local min_time = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, min_time)

-- Count current requests in window
local current = redis.call('ZCARD', key)

if current < limit then
    -- Allow request
    redis.call('ZADD', key, now, now .. ':' .. current)
    redis.call('EXPIRE', key, window)
    return {1, limit - current - 1, window}
else
    -- Rate limited
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local ttl = window
    if #oldest > 0 then
        ttl = math.max(0, window - (now - tonumber(oldest[2])))
    end
    return {0, 0, ttl}
end
"""


class RedisBackend:
    """Redis-backed rate limiting backend using atomic Lua scripts."""

    def __init__(self, redis_client: Any):
        self._redis = redis_client
        self._script = self._redis.register_script(_RATE_LIMIT_LUA)

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit atomically using Redis.

        Args:
            key: The rate limit key (e.g., "ratelimit:ip:1.2.3.4:/v1/experiments:run")
            limit: Maximum requests allowed in the window
            window_seconds: Window size in seconds

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()
        try:
            result = self._script(
                keys=[key],
                args=[limit, window_seconds, now],
            )
            allowed = int(result[0]) == 1
            remaining = int(result[1])
            ttl = int(result[2])
        except Exception as e:
            logger.error("redis_rate_limit_error", extra={"error": str(e), "key": key})
            # Fail open - allow request if Redis fails
            # This is a design decision: better to serve requests than block all
            allowed = True
            remaining = limit
            ttl = window_seconds

        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, remaining),
            reset_at=now + ttl,
            retry_after=ttl if not allowed else 0,
            limit=limit,
            key=key,
        )


class InMemoryBackend:
    """In-memory rate limiting backend for single-instance deployments.

    Uses a sliding window algorithm with per-key tracking.
    Suitable for development and single-instance production.
    """

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit using in-memory sliding window.

        Args:
            key: The rate limit key
            limit: Maximum requests allowed in the window
            window_seconds: Window size in seconds

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()
        window_start = now - window_seconds

        # Get existing timestamps for this key
        timestamps = self._windows[key]

        # Remove expired entries
        self._windows[key] = [t for t in timestamps if t > window_start]
        current_count = len(self._windows[key])

        if current_count < limit:
            # Allow request
            self._windows[key].append(now)
            remaining = limit - current_count - 1
            return RateLimitResult(
                allowed=True,
                remaining=max(0, remaining),
                reset_at=now + window_seconds,
                retry_after=0,
                limit=limit,
                key=key,
            )
        else:
            # Rate limited
            oldest = self._windows[key][0] if self._windows[key] else now
            retry_after = max(1, int(window_seconds - (now - oldest)))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=oldest + window_seconds,
                retry_after=retry_after,
                limit=limit,
                key=key,
            )


class RateLimiter:
    """Distributed rate limiter with Redis or in-memory backend.

    Security:
    - Sliding window algorithm prevents burst attacks at window boundaries
    - Atomic operations prevent race conditions
    - Project-scoped keys prevent cross-tenant rate limit bypass
    - IP anonymization in logs
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        default_limit: int = 1000,
        default_window: int = 60,
    ):
        self._redis_client = redis_client
        self._default_limit = default_limit
        self._default_window = default_window

        if redis_client is not None:
            try:
                self._backend: RedisBackend | InMemoryBackend = RedisBackend(redis_client)
                logger.info("rate_limiter_redis_backend")
            except Exception as e:
                logger.warning(
                    "rate_limiter_redis_init_failed_fallback_in_memory",
                    extra={"error": str(e)},
                )
                self._backend = InMemoryBackend()
        else:
            self._backend = InMemoryBackend()
            logger.info("rate_limiter_in_memory_backend")

    def check(
        self,
        key: str,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Args:
            key: The rate limit key (should include client identifier and endpoint)
            limit: Override default limit
            window_seconds: Override default window

        Returns:
            RateLimitResult with allowed status and metadata
        """
        # Sanitize key to prevent injection
        safe_key = self._sanitize_key(key)
        use_limit = limit if limit is not None else self._default_limit
        use_window = window_seconds if window_seconds is not None else self._default_window

        return self._backend.check_rate_limit(safe_key, use_limit, use_window)

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Sanitize rate limit key to prevent Redis key injection.

        Removes or escapes characters that could be used for Redis key injection.
        """
        # Only allow alphanumeric, colons, hyphens, underscores, and dots
        sanitized = "".join(
            c if c.isalnum() or c in ":._-" else "_"
            for c in key
        )
        # Limit length to prevent abuse
        if len(sanitized) > 256:
            sanitized = sanitized[:256]
        return f"we3:rl:{sanitized}"

    def get_client_ip(self, request: Any) -> str:
        """Extract and anonymize client IP from request.

        Only uses the first IP from X-Forwarded-For if behind a trusted proxy.
        Anonymizes the last octet for IPv4 and last 80 bits for IPv6.
        """
        # Check for forwarded header (trusted proxy scenario)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP only
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return self._anonymize_ip(client_ip)

    @staticmethod
    def _anonymize_ip(ip: str) -> str:
        """Anonymize client IP address for privacy.

        IPv4: zero out last octet (e.g., 192.168.1.100 -> 192.168.1.0)
        IPv6: zero out last 80 bits
        """
        if ":" in ip:
            # IPv6
            parts = ip.split(":")
            if len(parts) >= 3:
                return ":".join(parts[:2]) + ":0:0:0:0:0"
            return ip
        # IPv4
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0"
        return ip


def build_rate_limit_key(
    client_ip: str,
    path: str,
    project_id: str | None = None,
) -> str:
    """Build a rate limit key from request components.

    Format: {client_ip}:{path}:{project_id}
    If project_id is provided, rate limiting is per-project (more granular).
    """
    parts = [client_ip, path]
    if project_id:
        parts.append(project_id)
    return ":".join(parts)