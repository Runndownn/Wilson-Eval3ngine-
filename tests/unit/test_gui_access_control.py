from __future__ import annotations

import asyncio
from typing import Any

import pytest

from wilson_eval3ngine.gui import access_control
from wilson_eval3ngine.gui.access_control import GUIAccessSettings, GUIIdentityMiddleware


def _run(
    middleware: GUIIdentityMiddleware,
    *,
    scope_type: str = "http",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    captured: dict[str, Any] = {}

    async def app(scope, receive, send):
        captured.update(scope.get("state", {}))
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
        else:
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    middleware.app = app

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": scope_type,
        "path": "/api/test",
        "method": "GET",
        "headers": headers or [],
        "state": {},
    }
    asyncio.run(middleware(scope, receive, send))
    return sent, captured


def test_local_mode_stamps_loopback_operator_context() -> None:
    middleware = GUIIdentityMiddleware(lambda *_args: None, GUIAccessSettings(mode="local"))
    sent, captured = _run(middleware)

    assert sent[0]["status"] == 204
    assert captured["we3_actor"]["auth_method"] == "loopback"
    assert captured["we3_actor"]["role"] == "project_admin"


def test_remote_mode_rejects_missing_http_and_websocket_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuthenticator:
        def __init__(self, _settings):
            pass

    monkeypatch.setattr(access_control, "OIDCAuthenticator", FakeAuthenticator)
    settings = GUIAccessSettings(
        mode="oidc",
        issuer="https://issuer.invalid",
        jwks_uri="https://issuer.invalid/jwks",
        audience="gui",
    )
    middleware = GUIIdentityMiddleware(lambda *_args: None, settings)

    http_sent, _ = _run(middleware)
    websocket_sent, _ = _run(middleware, scope_type="websocket")

    assert http_sent[0]["status"] == 401
    assert websocket_sent == [
        {"type": "websocket.close", "code": 4401, "reason": "access denied"}
    ]


def test_remote_mode_accepts_verified_allowed_role(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuthenticator:
        def __init__(self, _settings):
            pass

        def authenticate(self, token: str) -> tuple[str, str]:
            assert token == "signed-token"
            return "project-a", "reviewer"

        def get_token_subject(self, token: str) -> str:
            assert token == "signed-token"
            return "actor-123"

    monkeypatch.setattr(access_control, "OIDCAuthenticator", FakeAuthenticator)
    middleware = GUIIdentityMiddleware(
        lambda *_args: None,
        GUIAccessSettings(
            mode="oidc",
            issuer="https://issuer.invalid",
            jwks_uri="https://issuer.invalid/jwks",
            audience="gui",
            allowed_roles=frozenset({"reviewer"}),
        ),
    )

    sent, captured = _run(
        middleware,
        headers=[(b"authorization", b"Bearer signed-token")],
    )

    assert sent[0]["status"] == 204
    assert captured["we3_actor"] == {
        "subject": "actor-123",
        "project_id": "project-a",
        "role": "reviewer",
        "auth_method": "oidc",
    }


def test_remote_mode_denies_verified_but_unapproved_role(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuthenticator:
        def __init__(self, _settings):
            pass

        def authenticate(self, _token: str) -> tuple[str, str]:
            return "project-a", "viewer"

        def get_token_subject(self, _token: str) -> str:
            return "actor-123"

    monkeypatch.setattr(access_control, "OIDCAuthenticator", FakeAuthenticator)
    middleware = GUIIdentityMiddleware(
        lambda *_args: None,
        GUIAccessSettings(
            mode="oidc",
            issuer="https://issuer.invalid",
            jwks_uri="https://issuer.invalid/jwks",
            audience="gui",
            allowed_roles=frozenset({"project_admin"}),
        ),
    )

    sent, _ = _run(middleware, headers=[(b"authorization", b"Bearer signed-token")])
    assert sent[0]["status"] == 403


def test_remote_settings_fail_closed_when_incomplete() -> None:
    with pytest.raises(ValueError, match="requires"):
        GUIAccessSettings(mode="oidc").validate()
