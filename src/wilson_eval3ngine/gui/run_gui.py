#!/usr/bin/env python3
"""Run the Wilson Eval3ngine GUI server."""

from __future__ import annotations

import logging

import uvicorn

from wilson_eval3ngine.gui.server import app, GUI_STATIC_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("we3.gui")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Wilson Eval3ngine GUI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--stay", action="store_true", help="Run in persistent background mode")
    args = parser.parse_args()

    logger.info("Starting Wilson Eval3ngine GUI at http://%s:%d", args.host, args.port)
    logger.info("Serving static files from: %s", GUI_STATIC_DIR)

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
