from __future__ import annotations

import socket

import httpx
import pytest

from wilson_eval3ngine.gui import runtime


def _records(*addresses: str):
    result = []
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        result.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
    return result


def test_public_https_destination_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WE3_GUI_ALLOW_LOCAL_PROVIDERS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _records("93.184.216.34"))
    runtime._validate_outbound_url("https://provider.example/v1/models")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.8",
        "172.16.0.8",
        "192.168.1.8",
        "::1",
        "fd00::8",
    ],
)
def test_local_destination_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    monkeypatch.delenv("WE3_GUI_ALLOW_LOCAL_PROVIDERS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _records(address))
    with pytest.raises(httpx.ConnectError, match="require WE3_GUI_ALLOW_LOCAL_PROVIDERS=1"):
        runtime._validate_outbound_url("http://local-provider.test:11434/api/tags")


@pytest.mark.parametrize("address", ["192.168.50.10", "::1"])
def test_explicit_local_mode_allows_private_and_loopback_provider(
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    monkeypatch.setenv("WE3_GUI_ALLOW_LOCAL_PROVIDERS", "1")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _records(address))
    runtime._validate_outbound_url("http://local-provider.test:11434/api/tags")


@pytest.mark.parametrize("address", ["169.254.169.254", "fe80::1", "224.0.0.1", "0.0.0.0"])
def test_never_allowed_ranges_remain_blocked_in_local_mode(
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    monkeypatch.setenv("WE3_GUI_ALLOW_LOCAL_PROVIDERS", "1")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: _records(address))
    with pytest.raises(httpx.ConnectError, match="prohibited address range"):
        runtime._validate_outbound_url("http://blocked.test/resource")


def test_any_unsafe_dns_answer_rejects_entire_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WE3_GUI_ALLOW_LOCAL_PROVIDERS", raising=False)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: _records("93.184.216.34", "127.0.0.1"),
    )
    with pytest.raises(httpx.ConnectError):
        runtime._validate_outbound_url("https://rebinding.example/v1")


def test_dns_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise socket.gaierror("not found")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(httpx.ConnectError, match="could not be resolved"):
        runtime._validate_outbound_url("https://missing.example/v1")


def test_metadata_hostname_is_rejected_before_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: pytest.fail("metadata host must not be resolved"),
    )
    with pytest.raises(httpx.ConnectError, match="metadata"):
        runtime._validate_outbound_url("http://metadata.google.internal/computeMetadata/v1")


@pytest.mark.asyncio
async def test_policy_client_disables_redirect_following(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_validate_outbound_url", lambda value: None)

    observed = {}

    async def fake_request(self, method, url, *args, **kwargs):
        observed.update(kwargs)
        return httpx.Response(302, request=httpx.Request(method, str(url)))

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    async with runtime._PolicyAsyncClient() as client:
        await client.get("https://provider.example/start", follow_redirects=True)

    assert observed["follow_redirects"] is False


def test_api_key_masking_is_constant() -> None:
    assert runtime.legacy.mask_api_key("sk-first-secret") == "[redacted]"
    assert runtime.legacy.mask_api_key("different-last-secret") == "[redacted]"
