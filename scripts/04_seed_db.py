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
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_common import (
    REPO_ROOT,
    Benefit,
    DataImportRun,
    init_db,
    new_id,
    session_scope,
    settings,
)
from sahaayak_contracts import Domain, EligibilityCriteria, VerificationStatus

DEFAULT_INPUT = REPO_ROOT / "data" / "structured" / "benefits.jsonl"


def parse_date(value: object) -> date:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def build_benefit(row: dict) -> Benefit:
    criteria = EligibilityCriteria.model_validate(row.get("eligibility_initial") or {})
    renewal_raw = row.get("eligibility_renewal")
    renewal = (
        EligibilityCriteria.model_validate(renewal_raw).model_dump(mode="json")
        if renewal_raw
        else None
    )

    raw_status = row.get("verification_status", VerificationStatus.MACHINE_STRUCTURED.value)
    status = VerificationStatus(raw_status)
    source_document_url = row.get("source_document_url") or row.get("source_url", "")

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
        verification_status=status,
        source_title=row.get("source_title", ""),
        source_document_url=source_document_url,
        source_excerpt=row.get("source_excerpt"),
        source_content_hash=row.get("source_content_hash"),
        automated_review=dict(row.get("automated_review") or {}),
        verified_by=row.get("verified_by"),
        verified_at=parse_datetime(row.get("verified_at")),
        valid_from=parse_date(row["valid_from"]) if row.get("valid_from") else None,
        valid_until=parse_date(row["valid_until"]) if row.get("valid_until") else None,
        is_active=bool(row.get("is_active", status is VerificationStatus.HUMAN_VERIFIED)),
        localized_summary=dict(row.get("localized_summary") or {}),
        job_metadata=dict(row.get("job_metadata") or {}) or None,
    )


def import_benefit(db, benefit: Benefit) -> str:
    """Merge one row without overwriting verified data."""
    existing = db.get(Benefit, benefit.id)
    incoming_hash = benefit.source_content_hash
    if existing and existing.verification_status is VerificationStatus.HUMAN_VERIFIED:
        same_source = bool(
            incoming_hash
            and existing.source_content_hash
            and incoming_hash == existing.source_content_hash
        )
        if (
            benefit.verification_status is not VerificationStatus.HUMAN_VERIFIED
            or not same_source
        ):
            # A rerun is never allowed to replace a verified row unless it is an
            # explicitly reviewed version of the identical source.
            return "protected_verified"

    changed_source = bool(
        existing
        and existing.source_content_hash
        and incoming_hash
        and existing.source_content_hash != incoming_hash
        and existing.verification_status is not VerificationStatus.HUMAN_VERIFIED
    )
    if changed_source:
        benefit.verification_status = VerificationStatus.NEEDS_REVIEW
        benefit.is_active = False

    db.merge(benefit)
    return "changed_source" if changed_source else "seeded"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"{args.file} not found — run steps 01 to 03 first.")

    init_db()
    ensure_reference_data()

    started_at = datetime.now(UTC)
    seeded, skipped = 0, 0
    unconstrained: list[str] = []
    changed_source_ids: list[str] = []
    protected_verified_ids: list[str] = []
    state_codes: set[str] = set()
    review_sample_size = 0

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

            outcome = import_benefit(db, benefit)
            if outcome == "protected_verified":
                protected_verified_ids.append(benefit.id)
                print(
                    f"  [HOLD] {benefit.id}: refusing to replace a human-verified "
                    "row with a new extraction"
                )
                continue
            if outcome == "changed_source":
                changed_source_ids.append(benefit.id)

            if benefit.verification_status is VerificationStatus.HUMAN_VERIFIED:
                review_sample_size += 1
            if benefit.state_code:
                state_codes.add(benefit.state_code)

            seeded += 1

            if not any(
                value not in (None, [], False, {})
                for key, value in benefit.eligibility_initial.items()
                if key != "exclusions"
            ):
                unconstrained.append(benefit.id)

        db.add(
            DataImportRun(
                id=new_id("imp"),
                source_name=str(args.file),
                state_code=next(iter(state_codes)) if len(state_codes) == 1 else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                model_name=settings.openai_structuring_model,
                prompt_version="structured-benefit-v1",
                input_count=seeded + skipped,
                accepted_count=seeded,
                failed_count=skipped,
                review_sample_size=review_sample_size,
                manifest_json={
                    "input_file": str(args.file),
                    "changed_source_ids": changed_source_ids,
                    "protected_verified_ids": protected_verified_ids,
                    "unconstrained_ids": unconstrained,
                },
            )
        )

    print(f"\nSeeded {seeded} benefits ({skipped} skipped) from {args.file}")
    if changed_source_ids:
        print(
            f"{len(changed_source_ids)} changed source rows were marked needs_review "
            "and deactivated."
        )
    if protected_verified_ids:
        print(
            f"{len(protected_verified_ids)} human-verified rows were protected from "
            "replacement."
        )

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
