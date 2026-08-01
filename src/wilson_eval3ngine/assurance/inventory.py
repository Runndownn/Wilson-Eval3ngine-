"""Deterministic, privacy-preserving byte-level repository inventory."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator

_DEFAULT_EXCLUDES = frozenset({
    ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".venv", "__pycache__", "build", "dist", "node_modules",
})
_BINARY_SUFFIXES = frozenset({
    ".7z", ".a", ".avi", ".bin", ".bz2", ".class", ".dll", ".dylib",
    ".exe", ".gif", ".gz", ".ico", ".jar", ".jpeg", ".jpg", ".mov",
    ".mp3", ".mp4", ".o", ".pdf", ".png", ".pyc", ".so", ".tar",
    ".tgz", ".ttf", ".woff", ".woff2", ".xz", ".zip",
})
_GENERATED_PREFIXES = ("artifacts/", "gui/static/charts/", "htmlcov/", "var/")


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    path: str
    kind: str
    size: int
    sha256: str
    mode: str
    executable: bool
    classification: str
    link_target: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryResult:
    schema_version: str
    root_name: str
    file_count: int
    symlink_count: int
    total_bytes: int
    bundle_sha256: str
    entries: tuple[InventoryEntry, ...]
    duplicate_sets: tuple[tuple[str, ...], ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "root_name": self.root_name,
            "file_count": self.file_count,
            "symlink_count": self.symlink_count,
            "total_bytes": self.total_bytes,
            "bundle_sha256": self.bundle_sha256,
            "entries": [asdict(entry) for entry in self.entries],
            "duplicate_sets": [list(group) for group in self.duplicate_sets],
            "errors": list(self.errors),
        }

    def write_json(self, destination: str | Path) -> None:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)


def _relative(path: Path, root: Path) -> str:
    return PurePosixPath(path.relative_to(root)).as_posix()


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _classify(relative: str, path: Path) -> str:
    lowered = relative.lower()
    if lowered.startswith(_GENERATED_PREFIXES):
        return "generated"
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return "binary"
    if "/vendor/" in f"/{lowered}/" or "/third_party/" in f"/{lowered}/":
        return "vendor"
    if lowered.startswith("tests/") or "/tests/" in f"/{lowered}/":
        return "test"
    if lowered.startswith("docs/") or path.suffix.lower() in {".md", ".rst"}:
        return "documentation"
    if path.suffix.lower() in {".cfg", ".ini", ".json", ".toml", ".yaml", ".yml"}:
        return "configuration"
    return "source"


def _paths(root: Path, excludes: frozenset[str]) -> Iterator[Path]:
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in excludes)
        base = Path(current)
        yield from (base / name for name in sorted(files))
        yield from (
            candidate
            for candidate in (base / name for name in sorted(directories))
            if candidate.is_symlink()
        )


def _safe_link_target(target: str) -> str:
    """Preserve useful relative topology without disclosing absolute host paths."""
    encoded = target.encode("utf-8", errors="surrogateescape")
    if Path(target).is_absolute():
        return "absolute-sha256:" + hashlib.sha256(encoded).hexdigest()
    return PurePosixPath(target.replace("\\", "/")).as_posix()


def _identity(entries: Iterable[InventoryEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        canonical = json.dumps(
            asdict(entry), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        digest.update(len(canonical).to_bytes(8, "big"))
        digest.update(canonical)
    return digest.hexdigest()


def build_inventory(
    root: str | Path,
    *,
    excludes: Iterable[str] = _DEFAULT_EXCLUDES,
    fail_on_error: bool = True,
) -> InventoryResult:
    """Account for every accessible regular file and symlink under ``root``.

    Symlinks are never followed. Absolute symlink targets are represented only
    by a digest, preventing workstation or deployment path disclosure. Special
    filesystem objects and read errors fail the inventory closed by default.
    """
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)

    entries: list[InventoryEntry] = []
    errors: list[str] = []
    for path in _paths(root_path, frozenset(excludes)):
        relative = _relative(path, root_path)
        try:
            metadata = path.lstat()
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISLNK(metadata.st_mode):
                raw_target = os.readlink(path)
                encoded = raw_target.encode("utf-8", errors="surrogateescape")
                entries.append(InventoryEntry(
                    relative, "symlink", len(encoded), hashlib.sha256(encoded).hexdigest(),
                    f"{mode:04o}", bool(mode & 0o111), "symlink",
                    _safe_link_target(raw_target),
                ))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("unsupported non-regular filesystem object")
            sha256, size = _hash_file(path)
            entries.append(InventoryEntry(
                relative, "file", size, sha256, f"{mode:04o}", bool(mode & 0o111),
                _classify(relative, path),
            ))
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}: {type(exc).__name__}")

    entries.sort(key=lambda item: item.path)
    by_content: dict[tuple[str, int], list[str]] = {}
    for entry in entries:
        if entry.kind == "file":
            by_content.setdefault((entry.sha256, entry.size), []).append(entry.path)
    duplicates = tuple(
        tuple(paths) for _key, paths in sorted(by_content.items()) if len(paths) > 1
    )
    if errors and fail_on_error:
        raise RuntimeError("inventory incomplete: " + "; ".join(errors))

    return InventoryResult(
        "we3.repository_inventory.v1",
        root_path.name,
        sum(entry.kind == "file" for entry in entries),
        sum(entry.kind == "symlink" for entry in entries),
        sum(entry.size for entry in entries if entry.kind == "file"),
        _identity(entries),
        tuple(entries),
        duplicates,
        tuple(errors),
    )


def verify_inventory(root: str | Path, expected: dict[str, object]) -> InventoryResult:
    actual = build_inventory(root)
    expected_hash = str(expected.get("bundle_sha256", ""))
    if not expected_hash:
        raise ValueError("expected inventory has no bundle_sha256")
    if actual.bundle_sha256 != expected_hash:
        raise RuntimeError(
            f"repository inventory drift: expected {expected_hash}, "
            f"observed {actual.bundle_sha256}"
        )
    return actual
