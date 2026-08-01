"""Conftest for environment emulation package.

This package provides fixtures for environment emulation.
The fixtures are registered via the top-level conftest.py via pytest_plugins.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the environment package is importable
ENV_ROOT = Path(__file__).resolve().parent
if str(ENV_ROOT) not in sys.path:
    sys.path.insert(0, str(ENV_ROOT))
