from __future__ import annotations

import pytest

from wilson_eval3ngine.gui.run_gui import validate_bind_host


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
    with pytest.raises(ValueError, match="loopback|Remote bind"):
        validate_bind_host(value)
