"""Bootstrap the Render Free demo database after migrations.

Migrations alone leave zero benefits, so visitors see "0 benefits loaded" and
cannot get eligibility matches. Launch languages are also limited to en/hi/kn
until release evidence is approved.

When RENDER_DEMO_BOOTSTRAP=true (set in render.yaml), this script:

1. Seeds illustrative demo benefits if no active benefits exist.
2. Opens planned languages + clears state_rollout targeting for the short demo.

Demo scaffolding only — not a substitute for reviewed ingestion.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlmodel import func, select

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_agent.languages import ALL_PROFILES, PLANNED_PROFILES
from sahaayak_common import (
    Benefit,
    FeatureFlag,
    Language,
    LanguageReadinessReview,
    init_db,
    session_scope,
)
from sahaayak_contracts import VerificationStatus

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from seed_demo import DEMO_BENEFITS  # noqa: E402


def _truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _active_benefit_count() -> int:
    with session_scope() as db:
        return int(
            db.exec(
                select(func.count()).select_from(Benefit).where(Benefit.is_active.is_(True))
            ).one()
            or 0
        )


def _seed_demo_benefits() -> int:
    with session_scope() as db:
        for entry in DEMO_BENEFITS:
            db.merge(
                Benefit(
                    **entry,
                    eligibility_renewal=None,
                    last_verified_date=date.today(),
                    verification_status=VerificationStatus.ILLUSTRATIVE,
                    source_title="myScheme reference (illustrative demo)",
                    source_document_url=entry.get("source_url", ""),
                    is_active=True,
                )
            )
    return len(DEMO_BENEFITS)


def _open_demo_catalog() -> None:
    """Activate planned languages and widen state rollout for the short demo."""
    now = datetime.now(UTC)
    planned_codes = {profile.code for profile in PLANNED_PROFILES}
    review_fields = (
        "native_speaker_status",
        "interface_status",
        "prompt_status",
        "content_status",
        "understanding_status",
        "voice_status",
        "accessibility_status",
    )
    with session_scope() as db:
        for profile in ALL_PROFILES:
            language = db.get(Language, profile.code)
            if language is None:
                continue
            language.is_active = True
            db.add(language)

            review = db.get(LanguageReadinessReview, profile.code)
            if review is None:
                review = LanguageReadinessReview(language_code=profile.code)
                db.add(review)
            needs_demo_attestation = profile.code in planned_codes or not all(
                getattr(review, field) == "approved" for field in review_fields
            )
            if needs_demo_attestation:
                for field in review_fields:
                    setattr(review, field, "approved")
                review.review_notes = (
                    "Render Free demo bootstrap — temporary activation for a "
                    "2–3 day public validation, not a production release attestation."
                )
                review.attestation = "render-demo-bootstrap"
                review.activated_at = review.activated_at or now
                db.add(review)

        ten = db.exec(select(FeatureFlag).where(FeatureFlag.key == "ten_language_rollout")).first()
        if ten is not None:
            ten.enabled = True
            ten.rollout_percentage = 100
            ten.target_languages = []
            db.add(ten)

        states = db.exec(select(FeatureFlag).where(FeatureFlag.key == "state_rollout")).first()
        if states is not None:
            # Empty target list means every state_code evaluates as in-scope.
            states.enabled = True
            states.rollout_percentage = 100
            states.target_states = []
            db.add(states)


def main() -> None:
    if not _truthy("RENDER_DEMO_BOOTSTRAP", "false"):
        print("RENDER_DEMO_BOOTSTRAP disabled; skipping demo bootstrap.")
        return

    init_db()
    ensure_reference_data()

    count = _active_benefit_count()
    if count == 0:
        seeded = _seed_demo_benefits()
        print(f"Seeded {seeded} illustrative demo benefits (catalog was empty).")
    else:
        print(f"Active benefits already present ({count}); leaving benefit rows unchanged.")

    if _truthy("RENDER_DEMO_OPEN_CATALOG", "true"):
        _open_demo_catalog()
        print(
            "Opened demo catalog: planned languages activated, "
            "ten_language_rollout on, state_rollout unrestricted."
        )
    else:
        print("RENDER_DEMO_OPEN_CATALOG disabled; launch languages only (en/hi/kn).")


if __name__ == "__main__":
    main()
