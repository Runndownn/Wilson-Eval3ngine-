from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from wilson_eval3ngine.assurance.inventory import build_inventory, verify_inventory


def test_inventory_is_content_deterministic_and_path_private(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "a.txt").write_text("alpha", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "b.txt").write_text("alpha", encoding="utf-8")

    first = build_inventory(root)
    os.utime(root / "a.txt", None)
    second = build_inventory(root)

    assert first.bundle_sha256 == second.bundle_sha256
    assert first.file_count == 2
    assert first.total_bytes == 10
    assert first.duplicate_sets == (("a.txt", "nested/b.txt"),)
    serialized = json.dumps(first.to_dict())
    assert str(tmp_path) not in serialized


def test_inventory_hash_changes_when_bytes_change(tmp_path: Path) -> None:
    target = tmp_path / "value.txt"
    target.write_text("one", encoding="utf-8")
    before = build_inventory(tmp_path)
    target.write_text("two", encoding="utf-8")
    after = build_inventory(tmp_path)
    assert before.bundle_sha256 != after.bundle_sha256


def test_verify_inventory_fails_closed_on_drift(tmp_path: Path) -> None:
    target = tmp_path / "value.txt"
    target.write_text("one", encoding="utf-8")
    expected = build_inventory(tmp_path).to_dict()
    target.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="inventory drift"):
        verify_inventory(tmp_path, expected)


def test_absolute_symlink_target_is_hashed_and_never_followed(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    outside = tmp_path.parent / "outside-inventory-test.txt"
    outside.write_text("private", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")

    result = build_inventory(tmp_path)
    entry = next(item for item in result.entries if item.path == "link")

    assert entry.kind == "symlink"
    assert entry.link_target is not None
    assert entry.link_target.startswith("absolute-sha256:")
    assert str(outside) not in json.dumps(result.to_dict())
    assert result.file_count == 0
