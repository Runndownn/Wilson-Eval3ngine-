from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def foundation_manifest(repo_root: Path) -> Path:
    return repo_root / "examples" / "experiments" / "foundation.yaml"


@pytest.fixture
def governance_path(repo_root):
    """Return path to governance directory."""
    return repo_root / "governance"


@pytest.fixture
def compliance_path(governance_path):
    """Return path to compliance directory."""
    return governance_path / "compliance"