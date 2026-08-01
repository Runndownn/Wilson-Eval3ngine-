from __future__ import annotations

import sys
import types

import pytest

from wilson_eval3ngine.gui.secret_transport import store_api_key_pipe
from wilson_eval3ngine.gui.secret_transport_factory import (
    SecretTransportConfigurationError,
    select_secret_transport,
)


def test_posix_fifo_is_default_when_available() -> None:
    assert select_secret_transport(plugin="", platform_has_fifo=True) is store_api_key_pipe


def test_unsupported_platform_fails_closed_without_private_plugin() -> None:
    with pytest.raises(SecretTransportConfigurationError, match="requires a private"):
        select_secret_transport(plugin="", platform_has_fifo=False)


def test_private_plugin_is_loaded_through_narrow_factory_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("private_transport_test_plugin")

    def factory(api_key: str, endpoint_id: str, purpose: str):
        return object()

    module.create_transport = factory
    monkeypatch.setitem(sys.modules, module.__name__, module)

    selected = select_secret_transport(
        plugin="private_transport_test_plugin:create_transport",
        platform_has_fifo=False,
    )
    assert selected is factory


def test_malformed_private_plugin_spec_is_rejected() -> None:
    with pytest.raises(SecretTransportConfigurationError, match="module:factory"):
        select_secret_transport(plugin="not-a-factory", platform_has_fifo=False)
