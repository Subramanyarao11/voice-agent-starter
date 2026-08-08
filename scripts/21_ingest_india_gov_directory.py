"""Fetch India.gov department/district directory rows into a review snapshot.

Examples:
    uv run python scripts/21_ingest_india_gov_directory.py --state-code KA
    uv run python scripts/21_ingest_india_gov_directory.py --all-states
    uv run python scripts/16_import_department_directory.py \
        --file data/directory/snapshots/india-gov-YYYYMMDD.json

The generated records are intentionally pending and inactive. This command
does not publish a route and never treats a state or district portal as proof
of a specific scheme's eligibility. A reviewer must inspect the source in the
admin console before routing can use a record.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from india_gov_directory import (
    DEFAULT_ORGANIZATION_TYPES,
    IndiaGovDirectoryClient,
    normalize_records,
)

from sahaayak_agent.languages import DEFAULT_STATES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--state-code", action="append", help="state/UT code, e.g. KA")
    group.add_argument("--all-states", action="store_true")
    parser.add_argument(
        "--organization-type",
        action="append",
        dest="organization_types",
        choices=("E003", "E004", "E042", "SPMA"),
        help="repeat to select source categories (default: departments, directorates, districts)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON snapshot path; defaults to data/directory/snapshots",
    )
    args = parser.parse_args()

    requested_codes = (
        [code.strip().upper() for code in args.state_code or []]
        if args.state_code
        else [code for code, _, _ in DEFAULT_STATES]
    )
    organization_types = tuple(args.organization_types or DEFAULT_ORGANIZATION_TYPES)
    fetched_at = datetime.now(UTC)
    output = args.output or (
        Path(__file__).resolve().parents[1]
        / "data"
        / "directory"
        / "snapshots"
        / f"india-gov-{fetched_at:%Y%m%dT%H%M%SZ}.json"
    )

    client = IndiaGovDirectoryClient()
    try:
        states = {str(row.get("state_id", "")).upper(): row for row in client.states()}
        missing = [code for code in requested_codes if code not in states]
        if missing:
            raise SystemExit(
                "India.gov did not return requested state code(s): "
                f"{', '.join(missing)}"
            )

        entries: list[dict] = []
        state_counts: dict[str, int] = {}
        for state_code in requested_codes:
            raw_rows = client.state_records(
                state_code,
                organization_types=organization_types,
            )
            normalized = normalize_records(
                state=states[state_code],
                records=raw_rows,
                fetched_at=fetched_at,
            )
            entries.extend(normalized)
            state_counts[state_code] = len(normalized)
    finally:
        client.close()

    payload = {
        "source": {
            "name": "India.gov.in Integrated Government Online Directory",
            "url": "https://www.india.gov.in/directory/contact-directory",
            "api_url": "https://www.india.gov.in/directory/contact-directory/api",
            "fetched_at": fetched_at.isoformat(),
            "organization_types": list(organization_types),
            "state_codes": requested_codes,
        },
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"India.gov directory snapshot written to {output}: "
        f"{len(entries)} rows across {len(state_counts)} state/UT(s)."
    )
    for state_code, count in state_counts.items():
        print(f"  {state_code}: {count} rows")
    print(
        "Next: run scripts/16_import_department_directory.py with this file; "
        "incoming rows remain pending and inactive until reviewed."
    )


if __name__ == "__main__":
    main()
