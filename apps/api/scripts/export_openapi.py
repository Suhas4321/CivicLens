"""Export the deterministic OpenAPI contract or fail when it has drifted."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from civiclens.main import app

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


def render_contract() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_contract()

    if args.check:
        if not CONTRACT_PATH.exists() or CONTRACT_PATH.read_text() != rendered:
            print("OpenAPI contract drift detected; run scripts/export_openapi.py")
            return 1
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
