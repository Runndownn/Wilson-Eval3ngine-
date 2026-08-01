#!/usr/bin/env python3
"""Run the Wilson Eval3ngine operator GUI server."""

from __future__ import annotations

import ipaddress
import logging

import uvicorn

from wilson_eval3ngine.gui.access_control import (
    GUIAccessSettings,
    install_gui_access_control,
)
from wilson_eval3ngine.gui.runtime import app
from wilson_eval3ngine.gui.server import GUI_STATIC_DIR
from wilson_eval3ngine.gui.ux_overlay import install_ux_overlay

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("we3.gui")

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}
_LEGACY_WILDCARD_HOSTS = {"0.0.0.0", "::", "[::]"}


def validate_bind_host(host: str) -> str:
    """Return a canonical loopback bind host or reject remote exposure.

    The listener remains loopback-only in both local and OIDC modes. Remote
    users reach it through a separately configured TLS reverse proxy, while the
    application independently validates the signed identity token.
    """
    normalized = host.strip().lower().rstrip(".")
    if normalized in _LOOPBACK_NAMES:
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(
            "The operator GUI may bind only to loopback. Use 127.0.0.1, ::1, "
            "or localhost and place an authenticated TLS reverse proxy in front."
        ) from exc
    if not address.is_loopback:
        raise ValueError(
            "The operator GUI may bind only to loopback. Remote bind addresses "
            "bypass the intended proxy and host boundary."
        )
    return address.compressed


def resolve_launcher_host(host: str) -> tuple[str, bool]:
    """Translate only historical wildcard defaults to the secure loopback bind."""
    normalized = host.strip().lower().rstrip(".")
    if normalized in _LEGACY_WILDCARD_HOSTS:
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
    except ValueError as exc:
        parser.error(str(exc))

    if repaired_legacy_default:
        logger.warning(
            "Legacy wildcard GUI host %s was requested; binding securely to "
            "http://127.0.0.1:%d instead.",
            args.host,
            args.port,
        )

    # Install security composition before Uvicorn begins accepting requests.
    install_gui_access_control(app, access)
    install_ux_overlay(app, GUI_STATIC_DIR)

    logger.info(
        "Starting Wilson Eval3ngine GUI at http://%s:%d with access mode %s",
        bind_host,
        args.port,
        access.mode,
    )
    logger.info("Serving static files from: %s", GUI_STATIC_DIR)

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
