#!/usr/bin/env python3
"""Validate render-critical assets referenced by active public documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_DOCS = (
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "GETTING_STARTED.md",
    ROOT / "docs" / "FEATURES.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "STATUS.md",
    ROOT / "docs" / "GUI_AND_EVIDENCE_GUIDE.md",
    ROOT / "docs" / "DOCUMENTATION_AUDIT.md",
)

STATIC_DIAGRAM_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "ARCHITECTURE.md",
)

HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")


def _local_target(document: Path, raw_target: str) -> Path | None:
    target = unquote(raw_target.strip())
    if target.startswith(("http://", "https://", "data:", "#")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None
    return (document.parent / target).resolve()


def _validate_image(path: Path) -> str | None:
    if not path.is_file():
        return "missing"
    suffix = path.suffix.lower()
    header = path.read_bytes()[:32]
    if suffix == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "invalid PNG signature"
    if suffix == ".svg":
        text = path.read_text(encoding="utf-8", errors="strict").lstrip()
        if not text.startswith("<svg"):
            return "invalid SVG root"
    return None


def main() -> int:
    errors: list[str] = []
    checked_images = 0

    for document in ACTIVE_DOCS:
        if not document.is_file():
            errors.append(f"missing active document: {document.relative_to(ROOT)}")
            continue
        text = document.read_text(encoding="utf-8")
        image_refs = HTML_IMAGE_RE.findall(text) + MARKDOWN_IMAGE_RE.findall(text)
        for image_ref in image_refs:
            target = _local_target(document, image_ref)
            if target is None:
                continue
            checked_images += 1
            try:
                display = target.relative_to(ROOT)
            except ValueError:
                errors.append(
                    f"{document.relative_to(ROOT)}: image escapes repository: {image_ref}"
                )
                continue
            problem = _validate_image(target)
            if problem:
                errors.append(
                    f"{document.relative_to(ROOT)}: {image_ref}: {problem} ({display})"
                )

    for document in STATIC_DIAGRAM_DOCS:
        text = document.read_text(encoding="utf-8")
        if "```mermaid" in text.lower():
            errors.append(
                f"{document.relative_to(ROOT)}: Mermaid block found; use a static docs/assets/diagrams asset"
            )

    if errors:
        print("Documentation asset validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Documentation asset validation passed: {len(ACTIVE_DOCS)} documents, "
        f"{checked_images} local image references."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
