#!/usr/bin/env python3
"""Run the Wilson Eval3ngine operator GUI server."""

from __future__ import annotations

import ipaddress
import logging
import os

import uvicorn

from wilson_eval3ngine.gui import server as legacy
from wilson_eval3ngine.gui.access_control import GUIAccessSettings, install_gui_access_control
from wilson_eval3ngine.gui.runtime import app
from wilson_eval3ngine.gui.secret_transport_factory import (
    SecretTransportConfigurationError,
    install_secret_transport,
)
from wilson_eval3ngine.gui.ux_overlay import install_ux_overlay

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("we3.gui")

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}
_LEGACY_WILDCARD_HOSTS = {"0.0.0.0", "::", "[::]"}
_REMOTE_BIND_ENV = "WE3_GUI_ALLOW_REMOTE_BIND"


def _remote_bind_allowed() -> bool:
    """Check whether the operator has explicitly permitted non-loopback binding."""
    return os.environ.get(_REMOTE_BIND_ENV, "").strip().lower() in {"1", "true", "yes"}


def validate_bind_host(host: str) -> str:
    """Return a canonical bind host or reject remote exposure when not permitted.

    By default only loopback addresses are accepted. When the operator sets
    ``WE3_GUI_ALLOW_REMOTE_BIND=1`` the check is relaxed so a specific LAN IP
    or a valid hostname may be used.
    """
    normalized = host.strip().lower().rstrip(".")
    if normalized in _LOOPBACK_NAMES:
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        # Not an IP — could be a hostname. Allow if remote bind is enabled.
        if _remote_bind_allowed():
            return normalized
        raise ValueError(
            "The operator GUI bind host must be a valid IP address or hostname."
        )
    if not address.is_loopback and not _remote_bind_allowed():
        raise ValueError(
            "The operator GUI may bind only to loopback. Set "
            f"{_REMOTE_BIND_ENV}=1 to permit a non-loopback bind address, or "
            "use 127.0.0.1 / localhost with an authenticated TLS reverse proxy."
        )
    return address.compressed


def resolve_launcher_host(host: str) -> tuple[str, bool]:
    """Translate only historical wildcard defaults to the secure loopback bind.

    When ``WE3_GUI_ALLOW_REMOTE_BIND=1`` is set, ``0.0.0.0`` is preserved so the
    server binds all interfaces as the operator explicitly requested.
    """
    normalized = host.strip().lower().rstrip(".")
    if normalized in _LEGACY_WILDCARD_HOSTS:
        if _remote_bind_allowed():
            return normalized, True
        return "127.0.0.1", True
    return validate_bind_host(host), False


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Wilson Eval3ngine GUI")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Loopback bind address only. Use an authenticated TLS reverse proxy for remote access.",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--stay", action="store_true", help="Run in persistent background mode")
    args = parser.parse_args()

    try:
        bind_host, repaired_legacy_default = resolve_launcher_host(args.host)
        access = GUIAccessSettings.from_env()
        access.validate()
        transport = install_secret_transport(legacy)
    except (ValueError, SecretTransportConfigurationError) as exc:
        parser.error(str(exc))

    if repaired_legacy_default:
        if bind_host == "0.0.0.0":
            logger.warning(
                "Legacy wildcard GUI host %s was requested; binding to all "
                "interfaces http://0.0.0.0:%d because %s=1 is set. "
                "Ensure this listener is behind a trusted firewall or "
                "authenticated TLS reverse proxy.",
                args.host, args.port, _REMOTE_BIND_ENV,
            )
        else:
            logger.warning(
                "Legacy wildcard GUI host %s was requested; binding securely "
                "to http://127.0.0.1:%d instead.",
                args.host, args.port,
            )

    install_gui_access_control(app, access)
    install_ux_overlay(app, legacy.GUI_STATIC_DIR)

    logger.info(
        "Starting Wilson Eval3ngine GUI at http://%s:%d with access mode %s "
        "and secret transport %s",
        bind_host,
        args.port,
        access.mode,
        getattr(transport, "__name__", type(transport).__name__),
    )
    logger.info("Serving static files from: %s", legacy.GUI_STATIC_DIR)

    config = uvicorn.Config(
        app,
        host=bind_host,
        port=args.port,
        log_level="info",
        reload=False,
        server_header=False,
        date_header=True,
        ws_max_size=1_000_000,
        timeout_keep_alive=10,
    )
    uvicorn.Server(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
