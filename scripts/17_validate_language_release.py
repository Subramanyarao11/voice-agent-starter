"""Validate prompt and native-review evidence for a language release.

The command is intentionally a gate, not an activation command. It reports
what is missing; an admin must still approve the evidence and activate the
locale through the audited admin endpoint.

Usage:
    uv run python scripts/17_validate_language_release.py --code ta
    uv run python scripts/17_validate_language_release.py --all
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_agent.languages import ALL_PROFILES
from sahaayak_agent.prompts import bundle_review_status, missing_keys, supported_languages
from sahaayak_common import Language, LanguageReadinessReview, init_db, session_scope

REVIEW_FIELDS = (
    "native_speaker_status",
    "interface_status",
    "prompt_status",
    "content_status",
    "understanding_status",
    "voice_status",
    "accessibility_status",
)


@dataclass
class ReleaseCheck:
    code: str
    prompt_bundle: bool
    prompt_bundle_status: str
    missing_prompt_keys: list[str]
    review_complete: bool
    review_statuses: dict[str, str]
    evidence_url: str
    reviewer: str | None
    reviewed_at: str | None
    database_active: bool
    ready: bool
    blockers: list[str]


def check_language(code: str) -> ReleaseCheck:
    normalized = code.strip().lower()
    profile_codes = {profile.code for profile in ALL_PROFILES}
    if normalized not in profile_codes:
        raise ValueError(f"unknown language code: {normalized}")

    prompt_bundle = normalized in supported_languages()
    missing = missing_keys(normalized) if prompt_bundle else []
    with session_scope() as db:
        language = db.get(Language, normalized)
        review = db.get(LanguageReadinessReview, normalized)
        statuses = {
            field: getattr(review, field, "missing") for field in REVIEW_FIELDS
        }
        evidence_url = review.evidence_url if review else ""
        reviewer = review.reviewed_by if review else None
        reviewed_at = review.reviewed_at.isoformat() if review and review.reviewed_at else None
        database_active = bool(language and language.is_active)

    review_complete = all(value == "approved" for value in statuses.values())
    blockers: list[str] = []
    if not prompt_bundle:
        blockers.append("prompt bundle is missing")
    if missing:
        blockers.append(f"{len(missing)} prompt keys are missing")
    if review is None:
        blockers.append("admin review record is missing")
    else:
        if not review_complete:
            blockers.append("native/content/voice/accessibility review is incomplete")
        if not evidence_url.strip():
            blockers.append("review evidence URL is missing")
        if reviewed_at is None:
            blockers.append("review timestamp is missing")
    if not database_active:
        blockers.append("locale is not explicitly activated")

    return ReleaseCheck(
        code=normalized,
        prompt_bundle=prompt_bundle,
        prompt_bundle_status=bundle_review_status(normalized),
        missing_prompt_keys=missing,
        review_complete=review_complete,
        review_statuses=statuses,
        evidence_url=evidence_url,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        database_active=database_active,
        ready=not blockers,
        blockers=blockers,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--code", action="append", dest="codes")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    init_db()
    ensure_reference_data()
    codes = (
        [profile.code for profile in ALL_PROFILES]
        if args.all
        else (args.codes or [])
    )
    results = [check_language(code) for code in codes]
    if args.as_json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = "READY" if result.ready else "BLOCKED"
            print(f"{result.code}: {status}")
            for blocker in result.blockers:
                print(f"  - {blocker}")
    if not all(result.ready for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
