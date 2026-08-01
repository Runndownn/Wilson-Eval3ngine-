"""Validation for immutable OCI/Docker image references."""

from __future__ import annotations

import re
from collections.abc import Iterable

_DIGEST_REFERENCE = re.compile(
    r"^(?P<name>[a-zA-Z0-9][a-zA-Z0-9._:/-]*)@sha256:(?P<digest>[a-f0-9]{64})$"
)


def validate_image_reference(reference: str) -> str:
    """Return a normalized immutable image reference or fail closed."""
    value = reference.strip()
    if value != reference or not value:
        raise ValueError("image reference must be non-empty and whitespace-free")
    match = _DIGEST_REFERENCE.fullmatch(value)
    if not match:
        raise ValueError("image reference must end in @sha256:<64 lowercase hex>")
    name = match.group("name")
    if "//" in name or name.startswith(("http:", "https:")):
        raise ValueError("image reference must not use a URL scheme")
    return value


def validate_image_references(references: Iterable[str]) -> tuple[str, ...]:
    validated = tuple(validate_image_reference(value) for value in references)
    if not validated:
        raise ValueError("at least one image reference is required")
    if len(set(validated)) != len(validated):
        raise ValueError("duplicate image references are not allowed")
    return validated


__all__ = ["validate_image_reference", "validate_image_references"]
