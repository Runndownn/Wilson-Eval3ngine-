from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable

from wilson_eval3ngine.api import middleware
from wilson_eval3ngine.api.body_limit import StreamingBodyLimitMiddleware


def _invoke(
    chunks: Iterable[bytes],
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    limit: int = 8,
) -> tuple[list[dict], list[bytes]]:
    chunk_list = list(chunks)
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunk_list) - 1,
        }
        for index, chunk in enumerate(chunk_list)
    ]
    received_by_app: list[bytes] = []
    sent: list[dict] = []

    async def app(scope, receive, send):
        del scope
        while True:
            message = await receive()
            received_by_app.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/test",
        "headers": headers or [],
    }
    asyncio.run(
        StreamingBodyLimitMiddleware(app, max_body_size=limit)(scope, receive, send)
    )
    return sent, received_by_app


def _response(sent: list[dict]) -> tuple[int, dict]:
    start = next(item for item in sent if item["type"] == "http.response.start")
    body = b"".join(
        item.get("body", b"")
        for item in sent
        if item["type"] == "http.response.body"
    )
    return start["status"], json.loads(body or b"{}")


def test_chunked_body_is_limited_by_actual_bytes() -> None:
    sent, received = _invoke([b"12345", b"6789"], limit=8)

    status, payload = _response(sent)
    assert status == 413
    assert payload["code"] == "payload_too_large"
    assert received == [b"12345"]


def test_declared_oversized_body_is_rejected_before_application_read() -> None:
    sent, received = _invoke(
        [b"ignored"],
        headers=[(b"content-length", b"9")],
        limit=8,
    )

    status, payload = _response(sent)
    assert status == 413
    assert payload["code"] == "payload_too_large"
    assert received == []


def test_conflicting_content_lengths_are_rejected() -> None:
    sent, received = _invoke(
        [b"1234"],
        headers=[(b"content-length", b"4"), (b"content-length", b"5")],
    )

    status, payload = _response(sent)
    assert status == 400
    assert payload["code"] == "conflicting_content_length"
    assert received == []


def test_body_at_limit_reaches_application() -> None:
    sent, received = _invoke([b"1234", b"5678"], limit=8)

    status, _payload = _response(sent)
    assert status == 204
    assert received == [b"1234", b"5678"]


def test_api_package_installs_streaming_implementation() -> None:
    assert middleware.BodySizeLimitMiddleware is StreamingBodyLimitMiddleware
