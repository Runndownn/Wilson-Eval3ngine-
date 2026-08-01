from __future__ import annotations

import pytest

from wilson_eval3ngine.assurance.image_references import (
    validate_image_reference,
    validate_image_references,
)


DIGEST = "a" * 64


def test_digest_pinned_reference_is_accepted() -> None:
    value = f"registry.example.invalid/team/image@sha256:{DIGEST}"
    assert validate_image_reference(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "python:3.13-slim",
        "python@sha256:short",
        f"https://registry.invalid/image@sha256:{DIGEST}",
        f" image@sha256:{DIGEST}",
        f"image@sha256:{DIGEST.upper()}",
        "",
    ],
)
def test_mutable_or_malformed_reference_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_image_reference(value)


def test_duplicate_reference_set_is_rejected() -> None:
    value = f"image@sha256:{DIGEST}"
    with pytest.raises(ValueError, match="duplicate"):
        validate_image_references([value, value])
