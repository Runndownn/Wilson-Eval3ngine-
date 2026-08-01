"""Authentication and role enforcement for the operator GUI.

Local mode relies on the launcher's loopback-only invariant. Remote mode
requires a reverse proxy to authenticate the browser and inject a signed OIDC
Bearer token on every HTTP and WebSocket request. The application validates the
token itself; unsigned identity headers are never trusted.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..security.oidc import OIDCAuthenticator, OIDCSettings, TokenValidationError

_DEFAULT_ROLES = frozenset({"project_admin", "evaluation_engineer", "reviewer"})


@dataclass(frozen=True, slots=True)
class GUIAccessSettings:
    mode: str = "local"
    issuer: str = ""
    jwks_uri: str = ""
    audience: str = "wilson-eval3ngine-gui"
    allowed_roles: frozenset[str] = _DEFAULT_ROLES

    @classmethod
    def from_env(cls) -> "GUIAccessSettings":
        roles = frozenset(
            value.strip()
            for value in os.environ.get(
                "WE3_GUI_ALLOWED_ROLES",
                ",".join(sorted(_DEFAULT_ROLES)),
            ).split(",")
            if value.strip()
        )
        return cls(
            mode=os.environ.get("WE3_GUI_ACCESS_MODE", "local").strip().lower(),
            issuer=os.environ.get("WE3_GUI_OIDC_ISSUER", "").strip(),
            jwks_uri=os.environ.get("WE3_GUI_OIDC_JWKS_URI", "").strip(),
            audience=os.environ.get(
                "WE3_GUI_OIDC_AUDIENCE", "wilson-eval3ngine-gui"
            ).strip(),
            allowed_roles=roles,
        )

    def validate(self) -> None:
        if self.mode not in {"local", "oidc"}:
            raise ValueError("WE3_GUI_ACCESS_MODE must be local or oidc")
        if self.mode == "oidc":
            missing = [
                name
                for name, value in {
                    "WE3_GUI_OIDC_ISSUER": self.issuer,
                    "WE3_GUI_OIDC_JWKS_URI": self.jwks_uri,
                    "WE3_GUI_OIDC_AUDIENCE": self.audience,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError("remote GUI identity requires " + ", ".join(missing))
            if not self.allowed_roles:
                raise ValueError("remote GUI identity requires at least one role")


class GUIIdentityMiddleware:
    """Authenticate HTTP and WebSocket requests at the application boundary."""

    def __init__(self, app: ASGIApp, settings: GUIAccessSettings) -> None:
        settings.validate()
        self.app = app
        self.settings = settings
        self.authenticator = (
            OIDCAuthenticator(
                OIDCSettings(
                    issuer=settings.issuer,
                    jwks_uri=settings.jwks_uri,
                    audience=settings.audience,
                )
            )
            if settings.mode == "oidc"
            else None
        )

    @staticmethod
    def _headers(scope: Scope) -> dict[bytes, bytes]:
        return {name.lower(): value for name, value in scope.get("headers", [])}

    @staticmethod
    def _bearer(scope: Scope) -> str | None:
        value = GUIIdentityMiddleware._headers(scope).get(b"authorization", b"")
        try:
            decoded = value.decode("ascii")
        except UnicodeDecodeError:
            return None
        if not decoded.startswith("Bearer "):
            return None
        token = decoded[7:].strip()
        return token or None

    @staticmethod
    async def _http_error(send: Send, status: int, code: str) -> None:
        body = json.dumps(
            {
                "schema_version": "we3.error.v1",
                "code": code,
                "retryable": False,
                "safe_detail": "GUI access denied",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
                (b"www-authenticate", b"Bearer"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _websocket_error(send: Send, code: int) -> None:
        await send({"type": "websocket.close", "code": code, "reason": "access denied"})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        if self.settings.mode == "local":
            state["we3_actor"] = {
                "subject": "local-operator",
                "project_id": "local",
                "role": "project_admin",
                "auth_method": "loopback",
            }
            await self.app(scope, receive, send)
            return

        token = self._bearer(scope)
        if token is None:
            if scope["type"] == "websocket":
                await self._websocket_error(send, 4401)
            else:
                await self._http_error(send, 401, "missing_bearer_token")
            return

        assert self.authenticator is not None
        try:
            project_id, role = self.authenticator.authenticate(token)
            subject = self.authenticator.get_token_subject(token)
        except TokenValidationError:
            if scope["type"] == "websocket":
                await self._websocket_error(send, 4401)
            else:
                await self._http_error(send, 401, "invalid_token")
            return

        if role not in self.settings.allowed_roles:
            if scope["type"] == "websocket":
                await self._websocket_error(send, 4403)
            else:
                await self._http_error(send, 403, "insufficient_role")
            return

        state["we3_actor"] = {
            "subject": subject,
            "project_id": project_id,
            "role": role,
            "auth_method": "oidc",
        }
        await self.app(scope, receive, send)


def install_gui_access_control(app: Any, settings: GUIAccessSettings | None = None) -> None:
    """Install identity once before the server begins accepting requests."""

    if getattr(app.state, "we3_gui_access_installed", False):
        return
    selected = settings or GUIAccessSettings.from_env()
    selected.validate()
    app.add_middleware(GUIIdentityMiddleware, settings=selected)
    app.state.we3_gui_access_settings = selected
    app.state.we3_gui_access_installed = True


__all__ = ["GUIAccessSettings", "GUIIdentityMiddleware", "install_gui_access_control"]
