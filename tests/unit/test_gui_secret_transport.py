from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from wilson_eval3ngine.gui import server
from wilson_eval3ngine.gui.secret_transport import OneShotSecretPipe, store_api_key_pipe
from wilson_eval3ngine.gui.ux_overlay import install_ux_overlay


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
def test_one_shot_secret_pipe_is_not_a_regular_file() -> None:
    handle = store_api_key_pipe("test-secret-value", "endpoint-1")
    path = Path(handle.file_path)
    try:
        mode = path.stat().st_mode
        assert stat.S_ISFIFO(mode)
        assert mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert handle.read_key() == "test-secret-value"
        assert handle._thread is not None
        handle._thread.join(timeout=1)
        assert not handle._thread.is_alive()
        assert all(value == 0 for value in handle._secret)
    finally:
        handle.destroy()

    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
def test_destroy_unblocks_writer_when_child_never_reads() -> None:
    handle = OneShotSecretPipe.create("cancelled-secret", "cancelled")
    path = Path(handle.file_path)

    handle.destroy()

    assert handle._thread is not None
    assert not handle._thread.is_alive()
    assert not path.exists()
    assert all(value == 0 for value in handle._secret)


def test_gui_composition_replaces_legacy_plaintext_transport(tmp_path: Path) -> None:
    from fastapi import FastAPI

    app = FastAPI()
    (tmp_path / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")

    original = server.store_api_key_temp_file
    try:
        install_ux_overlay(app, tmp_path)
        assert server.store_api_key_temp_file is store_api_key_pipe
    finally:
        server.store_api_key_temp_file = original


def test_secret_transport_rejects_empty_and_oversized_values() -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO required")

    with pytest.raises(ValueError, match="empty"):
        store_api_key_pipe("", "endpoint")
    with pytest.raises(ValueError, match="4096"):
        store_api_key_pipe("x" * 4097, "endpoint")
