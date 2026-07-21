#!/usr/bin/env python3
"""Stop the Wilson Eval3ngine GUI server."""

from __future__ import annotations

import json
import logging
import os
import signal
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("we3.gui.stop")


def find_gui_processes() -> list[dict[str, Any]]:
    candidates = []
    workspace = Path(__file__).resolve().parent.parent.parent
    target = str(workspace / "src" / "wilson_eval3ngine" / "gui" / "run_gui.py")
    try:
        import psutil
    except ImportError:
        return []

    for proc in psutil.process_iter(["pid", "name", "cmdline", "status"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if target in " ".join(cmdline):
                candidates.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "status": proc.info["status"],
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return candidates


def main() -> int:
    candidates = find_gui_processes()
    if not candidates:
        logger.info("No running Wilson Eval3ngine GUI processes found.")
        return 0

    for candidate in candidates:
        pid = candidate["pid"]
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to GUI process %d (%s)", pid, candidate["name"])
        except ProcessLookupError:
            logger.info("Process %d already exited", pid)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to stop process %d: %s", pid, exc)

    logger.info(json.dumps({"stopped": len(candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
