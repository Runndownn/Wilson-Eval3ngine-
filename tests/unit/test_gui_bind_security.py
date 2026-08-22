from __future__ import annotations

import pytest

from wilson_eval3ngine.gui.access_control import GUIAccessSettings
from wilson_eval3ngine.gui.run_gui import (
    resolve_launcher_host,
    validate_bind_host,
    validate_exposure_contract,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("127.0.0.1", "127.0.0.1"),
        ("127.42.7.9", "127.42.7.9"),
        ("::1", "::1"),
        ("LOCALHOST", "localhost"),
        ("localhost.", "localhost"),
    ],
)
def test_validate_bind_host_accepts_only_loopback(value: str, expected: str) -> None:
    assert validate_bind_host(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0.0.0.0",
        "::",
        "192.168.1.10",
        "10.0.0.5",
        "example.com",
        "",
    ],
)
def test_validate_bind_host_rejects_remote_or_ambiguous_targets(value: str) -> None:
    with pytest.raises(ValueError, match="loopback|valid IP address"):
        validate_bind_host(value)


def test_remote_bind_opt_in_does_not_disable_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WE3_GUI_ALLOW_REMOTE_BIND", "1")
    bind_host, _ = resolve_launcher_host("0.0.0.0")

    with pytest.raises(ValueError, match="requires WE3_GUI_ACCESS_MODE=oidc"):
        validate_exposure_contract(bind_host, GUIAccessSettings(mode="local"))


def test_remote_bind_is_accepted_only_with_validated_oidc_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WE3_GUI_ALLOW_REMOTE_BIND", "1")
    bind_host = validate_bind_host("192.168.10.20")
    access = GUIAccessSettings(
        mode="oidc",
        issuer="https://issuer.invalid",
        jwks_uri="https://issuer.invalid/jwks",
        audience="wilson-eval3ngine-gui",
        allowed_roles=frozenset({"project_admin"}),
    )
    access.validate()
    validate_exposure_contract(bind_host, access)


def test_loopback_remains_usable_with_local_operator_mode() -> None:
    validate_exposure_contract("127.0.0.1", GUIAccessSettings(mode="local"))
