#!/usr/bin/env python3
"""Verify a sanitized private-runtime evidence envelope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wilson_eval3ngine.assurance.runtime_evidence import verify_runtime_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence")
    args = parser.parse_args()

    payload = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    envelope = verify_runtime_evidence(payload)
    print(envelope.bundle_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
