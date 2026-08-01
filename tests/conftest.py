from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Register environment emulation fixtures
ENV_ROOT = REPO_ROOT / "tests" / "environment"
if str(ENV_ROOT) not in sys.path:
    sys.path.insert(0, str(ENV_ROOT))

pytest_plugins = ["environment.fixtures"]


@pytest.fixture(autouse=True)
def _no_fsync():
    """Disable os.fsync in tests — it hangs on certain filesystems and is an
    OS-level durability concern, not application logic."""
    with patch("os.fsync"):
        yield


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


# ---------------------------------------------------------------------------
# Shared database fixtures
#
# SQLite's create_all is extremely slow (~16s) when creating many indexes.
# These fixtures create the schema once per session in a shared in-memory
# database and roll back each test's transaction, giving every test a clean
# state without the overhead of recreating tables.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped engine with schema created once."""
    from wilson_eval3ngine.persistence.database import Base, Database

    db = Database(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.initialize()
    yield db
    db.engine.dispose()


@pytest.fixture
def db(db_engine):
    """Function-scoped database with transaction rollback for clean state.

    Sessions created via ``db.session()`` are bound to a connection that
    participates in a transaction rolled back after the test, ensuring
    every test starts with an empty database.
    """
    from sqlalchemy.orm import sessionmaker, Session
    from wilson_eval3ngine.persistence.database import Database

    connection = db_engine.engine.connect()
    transaction = connection.begin()

    db = Database.__new__(Database)
    db.engine = db_engine.engine
    db.session_factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=Session,
    )

    yield db

    # Rollback the transaction if still active (a test may have committed)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if transaction.is_active:
            transaction.rollback()
    connection.close()
