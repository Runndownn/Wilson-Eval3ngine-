#!/usr/bin/env python3
"""Run the Wilson Eval3ngine operator GUI server."""

from __future__ import annotations

import ipaddress
import logging

import uvicorn

from wilson_eval3ngine.gui.runtime import app
from wilson_eval3ngine.gui.server import GUI_STATIC_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("we3.gui")


_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}


def validate_bind_host(host: str) -> str:
    """Return a canonical loopback bind host or reject remote exposure.

    The operator GUI has no built-in user authentication and controls provider
    credentials, report-generation subprocesses, jobs, telemetry, and report
    deletion. The repository-provided launcher therefore fails closed unless
    the bind target is an explicit loopback address or well-known loopback
    hostname. Remote access must be provided by a separately authenticated TLS
    reverse proxy connecting to this loopback listener.
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
            "expose unauthenticated administrative controls."
        )
    return address.compressed


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
        bind_host = validate_bind_host(args.host)
    except ValueError as exc:
        parser.error(str(exc))

    logger.info("Starting Wilson Eval3ngine GUI at http://%s:%d", bind_host, args.port)
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
    server = uvicorn.Server(config)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
