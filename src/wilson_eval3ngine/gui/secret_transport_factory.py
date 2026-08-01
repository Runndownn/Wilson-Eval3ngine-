"""Cross-platform report-secret transport selection.

The public repository supplies the POSIX FIFO implementation. Platforms that
cannot provide ``os.mkfifo`` must inject a reviewed private transport plugin,
for example a Windows named-pipe implementation with deployment-specific ACLs.
No private pipe names, accounts, security descriptors, or topology belong here.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Callable, Protocol, runtime_checkable

from .secret_transport import OneShotSecretPipe, store_api_key_pipe


class SecretTransportConfigurationError(RuntimeError):
    pass


@runtime_checkable
class SecretTransportHandle(Protocol):
    file_path: str

    def destroy(self) -> None:
        ...


SecretTransportFactory = Callable[[str, str, str], SecretTransportHandle]


def _validate_factory(factory: Any) -> SecretTransportFactory:
    if not callable(factory):
        raise SecretTransportConfigurationError("secret transport factory is not callable")
    return factory


def _load_private_factory(spec: str) -> SecretTransportFactory:
    module_name, separator, factory_name = spec.partition(":")
    if not separator or not module_name or not factory_name:
        raise SecretTransportConfigurationError(
            "WE3_SECRET_TRANSPORT_PLUGIN must use module:factory syntax"
        )
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
    except Exception as exc:
        raise SecretTransportConfigurationError(
            "private secret transport plugin could not be loaded"
        ) from exc
    return _validate_factory(factory)


def select_secret_transport(
    *,
    plugin: str | None = None,
    platform_has_fifo: bool | None = None,
) -> SecretTransportFactory:
    """Return the authoritative one-shot child-secret transport factory.

    A configured plugin takes precedence, allowing a private implementation to
    be used on any platform after review. Without a plugin, POSIX FIFO support
    is mandatory and unsupported platforms fail closed.
    """

    spec = (plugin if plugin is not None else os.environ.get(
        "WE3_SECRET_TRANSPORT_PLUGIN", ""
    )).strip()
    if spec:
        return _load_private_factory(spec)

    fifo_available = hasattr(os, "mkfifo") if platform_has_fifo is None else platform_has_fifo
    if not fifo_available:
        raise SecretTransportConfigurationError(
            "this platform requires a private one-shot secret transport plugin"
        )
    return store_api_key_pipe


def install_secret_transport(target_module: Any) -> SecretTransportFactory:
    """Install the selected transport at the legacy dynamic call boundary."""

    factory = select_secret_transport()
    target_module.store_api_key_temp_file = factory
    return factory


__all__ = [
    "OneShotSecretPipe",
    "SecretTransportConfigurationError",
    "SecretTransportFactory",
    "SecretTransportHandle",
    "install_secret_transport",
    "select_secret_transport",
]
