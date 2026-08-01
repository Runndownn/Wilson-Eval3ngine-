#!/usr/bin/env python3
"""Validate immutable image references from arguments or standard input."""

from __future__ import annotations

import argparse
import sys

from wilson_eval3ngine.assurance.image_references import validate_image_references


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", nargs="*")
    args = parser.parse_args()

    references = args.references or [
        line.strip() for line in sys.stdin if line.strip()
    ]
    for reference in validate_image_references(references):
        print(reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
