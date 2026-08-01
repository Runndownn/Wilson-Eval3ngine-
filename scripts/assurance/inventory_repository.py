#!/usr/bin/env python3
"""Generate or verify a deterministic repository inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wilson_eval3ngine.assurance.inventory import build_inventory, verify_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--output", default="artifacts/assurance/repository-inventory.json")
    parser.add_argument("--verify", help="Existing inventory JSON to verify")
    args = parser.parse_args()

    if args.verify:
        expected = json.loads(Path(args.verify).read_text(encoding="utf-8"))
        result = verify_inventory(args.root, expected)
        print(result.bundle_sha256)
        return 0

    result = build_inventory(args.root)
    result.write_json(args.output)
    print(result.bundle_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
