"""Validate active benefit rows before a production data publish.

Usage:
    python scripts/validate_benefits.py
    python scripts/validate_benefits.py --allow-illustrative  # local demo only

The normal command intentionally rejects illustrative and machine-only rows.
That makes an accidental publish fail loudly instead of turning a development
seed into an implied government answer.
"""

from __future__ import annotations

import argparse
from datetime import date
from urllib.parse import urlparse

from pydantic import ValidationError
from sqlmodel import select

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_common import Benefit, State, init_db, session_scope
from sahaayak_contracts import EligibilityCriteria, VerificationStatus


def valid_source(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_benefit(
    benefit: Benefit,
    state_codes: set[str],
    *,
    allow_illustrative: bool,
) -> list[str]:
    errors: list[str] = []
    source_url = benefit.source_document_url or benefit.source_url

    if not valid_source(source_url):
        errors.append("missing or invalid source URL")
    try:
        EligibilityCriteria.model_validate(benefit.eligibility_initial or {})
    except ValidationError as exc:
        errors.append(f"invalid eligibility criteria: {exc.error_count()} errors")

    if benefit.state_code and benefit.state_code not in state_codes:
        errors.append(f"unsupported state code {benefit.state_code}")
    if benefit.valid_until and benefit.valid_until < date.today():
        errors.append(f"expired on {benefit.valid_until.isoformat()}")
    if benefit.verification_status is VerificationStatus.STALE:
        errors.append("row is marked stale")
    if (
        not allow_illustrative
        and benefit.verification_status is not VerificationStatus.HUMAN_VERIFIED
    ):
        errors.append(f"verification status is {benefit.verification_status.value}")
    if benefit.verification_status is VerificationStatus.HUMAN_VERIFIED:
        if benefit.verified_at is None:
            errors.append("human-verified row has no verified_at timestamp")
        if not benefit.verified_by:
            errors.append("human-verified row has no verified_by reviewer")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-illustrative",
        action="store_true",
        help="allow illustrative rows for local/demo validation only",
    )
    args = parser.parse_args()

    init_db()
    ensure_reference_data()

    with session_scope() as db:
        state_codes = {row.code for row in db.exec(select(State)).all()}
        rows = list(db.exec(select(Benefit).where(Benefit.is_active.is_(True))).all())
        failures = {
            row.id: validate_benefit(
                row,
                state_codes,
                allow_illustrative=args.allow_illustrative,
            )
            for row in rows
        }

    failures = {benefit_id: errors for benefit_id, errors in failures.items() if errors}
    if failures:
        print(f"Validation failed for {len(failures)} active benefit(s):")
        for benefit_id, errors in failures.items():
            for error in errors:
                print(f"  - {benefit_id}: {error}")
        raise SystemExit(1)

    print(
        f"Validated {len(rows)} active benefit(s) with "
        f"{('illustrative rows allowed' if args.allow_illustrative else 'human review required')}."
    )


if __name__ == "__main__":
    main()
