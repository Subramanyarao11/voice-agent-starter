"""Step 4: load structured benefits into the database.

Rows are validated against the eligibility contract on the way in. A row that
fails is reported and skipped rather than stored, because a malformed criteria
blob would otherwise sit in the table looking like data until it silently
matched nobody.

Usage:
    python scripts/04_seed_db.py
    python scripts/04_seed_db.py --file data/structured/benefits.jsonl
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_common import REPO_ROOT, Benefit, init_db, session_scope
from sahaayak_contracts import Domain, EligibilityCriteria

DEFAULT_INPUT = REPO_ROOT / "data" / "structured" / "benefits.jsonl"


def parse_date(value: object) -> date:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def build_benefit(row: dict) -> Benefit:
    criteria = EligibilityCriteria.model_validate(row.get("eligibility_initial") or {})
    renewal_raw = row.get("eligibility_renewal")
    renewal = (
        EligibilityCriteria.model_validate(renewal_raw).model_dump(mode="json")
        if renewal_raw
        else None
    )

    return Benefit(
        id=row["id"],
        domain=Domain(row.get("domain", Domain.SCHEME.value)),
        name=row["name"],
        state_code=row.get("state_code"),
        category=row.get("category", ""),
        description=row.get("description", ""),
        eligibility_initial=criteria.model_dump(mode="json"),
        eligibility_renewal=renewal,
        benefits_text=row.get("benefits_text", ""),
        documents_required=list(row.get("documents_required") or []),
        application_process=row.get("application_process", ""),
        source_url=row.get("source_url", ""),
        last_verified_date=parse_date(row.get("last_verified_date")),
        localized_summary=dict(row.get("localized_summary") or {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"{args.file} not found — run steps 01 to 03 first.")

    init_db()
    ensure_reference_data()

    seeded, skipped = 0, 0
    unconstrained: list[str] = []

    with open(args.file, encoding="utf-8") as handle, session_scope() as db:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                benefit = build_benefit(row)
            except (json.JSONDecodeError, ValidationError, KeyError) as exc:
                skipped += 1
                print(f"  [SKIP] line {line_number}: {exc}")
                continue

            # merge, not add: seeding is expected to be re-run as the pipeline
            # is refined, and it should update rather than collide.
            db.merge(benefit)
            seeded += 1

            if not any(
                value not in (None, [], False, {})
                for key, value in benefit.eligibility_initial.items()
                if key != "exclusions"
            ):
                unconstrained.append(benefit.id)

    print(f"\nSeeded {seeded} benefits ({skipped} skipped) from {args.file}")

    if unconstrained:
        # Not an error, but almost always an extraction miss: a real scheme with
        # zero stated conditions would qualify literally everyone.
        print(
            f"\n{len(unconstrained)} have no checkable eligibility criteria and will be "
            "reported at low confidence. Worth re-checking against their source text:"
        )
        for benefit_id in unconstrained[:10]:
            print(f"  - {benefit_id}")
        if len(unconstrained) > 10:
            print(f"  ... and {len(unconstrained) - 10} more")


if __name__ == "__main__":
    main()
