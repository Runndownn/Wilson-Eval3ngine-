from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the Wilson Eval3ngine development OpenAPI contract."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("contracts/openapi.v1.json"),
    )
    args = parser.parse_args()

    os.environ.setdefault("WE3_DATABASE_URL", "sqlite:///./var/openapi.db")
    os.environ.setdefault("WE3_ARTIFACT_ROOT", "./var/openapi-artifacts")

    from wilson_eval3ngine.api.main import app

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(app.openapi(), sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
