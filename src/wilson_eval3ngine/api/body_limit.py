"""ASGI request-body limits based on bytes actually received.

A declared Content-Length is only an optimization and cannot be the security
boundary: HTTP/1.1 chunked requests, HTTP/2 streams, malformed clients, and
proxy/backend disagreements may omit or contradict it.  This middleware wraps
the ASGI receive channel and enforces the configured limit before framework
body parsing or endpoint execution.
"""

from __future__ import annotations

import json
import os
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


class RequestBodyTooLarge(Exception):
    """Internal control-flow signal raised by the bounded receive channel."""


class StreamingBodyLimitMiddleware:
    """Reject HTTP request bodies that exceed the actual byte budget."""

    def __init__(self, app: ASGIApp, max_body_size: int | None = None) -> None:
        self.app = app
        configured = max_body_size
        if configured is None:
            configured = int(
                os.environ.get("WE3_MAX_BODY_SIZE", str(_DEFAULT_MAX_BODY_SIZE))
            )
        if configured <= 0:
            raise ValueError("max_body_size must be positive")
        self.max_body_size = configured

    @staticmethod
    def _content_lengths(scope: Scope) -> list[str]:
        values: list[str] = []
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    values.append(value.decode("ascii"))
                except UnicodeDecodeError:
                    values.append("")
        return values

    @staticmethod
    async def _send_json(
        send: Send,
        status: int,
        code: str,
        detail: str,
    ) -> None:
        payload = json.dumps(
            {
                "schema_version": "we3.error.v1",
                "code": code,
                "retryable": False,
                "safe_detail": detail,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        lengths = self._content_lengths(scope)
        if lengths:
            parsed: list[int] = []
            try:
                for raw in lengths:
                    if not raw or raw.strip() != raw:
                        raise ValueError
                    value = int(raw, 10)
                    if value < 0:
                        raise ValueError
                    parsed.append(value)
            except ValueError:
                await self._send_json(
                    send,
                    400,
                    "invalid_content_length",
                    "invalid Content-Length header",
                )
                return
            if len(set(parsed)) != 1:
                await self._send_json(
                    send,
                    400,
                    "conflicting_content_length",
                    "conflicting Content-Length headers",
                )
                return
            if parsed[0] > self.max_body_size:
                await self._send_json(
                    send,
                    413,
                    "payload_too_large",
                    "request body exceeds maximum allowed size",
                )
                return

        received = 0
        response_started = False

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received += len(body)
                if received > self.max_body_size:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except RequestBodyTooLarge:
            if not response_started:
                await self._send_json(
                    send,
                    413,
                    "payload_too_large",
                    "request body exceeds maximum allowed size",
                )
                return
            raise


__all__ = ["RequestBodyTooLarge", "StreamingBodyLimitMiddleware"]
