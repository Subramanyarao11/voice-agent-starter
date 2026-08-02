"""Write the API's OpenAPI schema to packages/api-types.

The web client's types are generated from the schema rather than hand-written,
so a change to a response model is a compile error in the frontend instead of a
runtime surprise. The schema is produced in-process, which means this does not
need a running server.

Usage:
    python scripts/generate_api_types.py
"""

from __future__ import annotations

import json
import subprocess
import sys

from sahaayak_api.main import app
from sahaayak_common import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "packages" / "api-types" / "openapi.json"
TYPES_PATH = REPO_ROOT / "packages" / "api-types" / "src" / "schema.d.ts"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    TYPES_PATH.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {SCHEMA_PATH.relative_to(REPO_ROOT)}")

    result = subprocess.run(
        ["npx", "--yes", "openapi-typescript", str(SCHEMA_PATH), "-o", str(TYPES_PATH)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # The schema is the source of truth and is already written; the
        # TypeScript step needs Node, which a Python-only checkout may not have.
        print("Could not run openapi-typescript:", result.stderr.strip(), file=sys.stderr)
        print("Install Node and re-run, or generate from the JSON schema by hand.")
        raise SystemExit(1)

    print(f"Wrote {TYPES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
