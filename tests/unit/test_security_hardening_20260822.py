from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from wilson_eval3ngine.persistence.audit import AuditLedger
from wilson_eval3ngine.persistence.database import Database
from wilson_eval3ngine.security.oidc import TokenRevocationList, TokenValidationError
from wilson_eval3ngine.security.rate_limit import (
    ClientIdentityResolver,
    RateLimitBackendUnavailable,
    RateLimiter,
    build_rate_limit_key,
)


def _request(peer: str, forwarded_for: str | None = None):
    headers: dict[str, str] = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_untrusted_peer_cannot_spoof_forwarded_client_identity() -> None:
    resolver = ClientIdentityResolver(["10.0.0.0/24"])
    assert resolver.resolve_address(
        _request("203.0.113.7", "198.51.100.9")
    ) == "203.0.113.7"


def test_trusted_proxy_chain_resolves_first_untrusted_client() -> None:
    resolver = ClientIdentityResolver(["10.0.0.0/24"])
    assert resolver.resolve_address(
        _request("10.0.0.5", "198.51.100.9, 10.0.0.4")
    ) == "198.51.100.9"


def test_pre_auth_rate_key_does_not_require_project_identity() -> None:
    first = build_rate_limit_key("198.51.100.9", "/v1/experiments:run")
    second = build_rate_limit_key("198.51.100.9", "/v1/experiments:run")
    assert first == second
    assert "project:" not in first


def test_authenticated_project_scope_can_have_distinct_secondary_bucket() -> None:
    first = build_rate_limit_key(
        "198.51.100.9", "/v1/experiments:run", "proj_a"
    )
    second = build_rate_limit_key(
        "198.51.100.9", "/v1/experiments:run", "proj_b"
    )
    assert first != second
    assert "proj_a" in first


def test_assurance_rate_limiter_requires_distributed_authority() -> None:
    with pytest.raises(RateLimitBackendUnavailable):
        RateLimiter(fail_closed=True)


def test_revocation_jti_is_bounded_before_redis_key_use() -> None:
    redis_client = Mock()
    revocations = TokenRevocationList(redis_client=redis_client)
    with pytest.raises(TokenValidationError):
        revocations.revoke("x" * 257, token_ttl=60)
    redis_client.setex.assert_not_called()


def test_revocation_preserves_requested_remaining_lifetime() -> None:
    redis_client = Mock()
    revocations = TokenRevocationList(redis_client=redis_client)
    revocations.revoke("token-123", token_ttl=7200)
    redis_client.setex.assert_called_once_with(
        "we3:token_revoked:token-123", 7200, "1"
    )


def test_sqlite_audit_chain_serializes_concurrent_project_appends(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'audit.db'}")
    database.initialize()
    ledger = AuditLedger(database)

    def append(index: int) -> None:
        ledger.append(
            project_id="proj_concurrency",
            event_type="concurrency_probe",
            aggregate_type="test",
            aggregate_id=str(index),
            actor_id="test-suite",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(32)))

    assert ledger.verify("proj_concurrency") is True
