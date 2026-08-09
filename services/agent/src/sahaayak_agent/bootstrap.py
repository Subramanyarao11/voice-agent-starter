"""Reference data the app needs before it can serve a single call.

Languages and states are configuration expressed as rows, so they are ensured
idempotently at startup rather than left to a migration someone has to remember
to run. Benefits are not seeded here — those come from the ingestion pipeline,
and inventing them would undercut the whole point of using real myScheme data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from sahaayak_agent.languages import ALL_PROFILES, DEFAULT_CATALOG, DEFAULT_STATES, PLANNED_PROFILES
from sahaayak_common import (
    FeatureFlag,
    Language,
    LanguageReadinessReview,
    State,
    ensure_benefit_baselines,
    ensure_default_feature_flags,
    ensure_directory_baselines,
    ensure_household_fact_definitions,
    get_logger,
    session_scope,
)

log = get_logger(__name__)


def open_demo_language_catalog() -> None:
    """Temporarily activate all registered languages for a short public demo.

    Approves readiness rows and enables ten_language_rollout. Not a production
    language-release attestation — use only behind RENDER_DEMO_OPEN_CATALOG.
    """
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
                    "Demo catalog open — temporary activation for short public "
                    "validation, not a production release attestation."
                )
                review.reviewed_by = "render-demo-bootstrap"
                review.reviewed_at = review.reviewed_at or now
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
            states.enabled = True
            states.rollout_percentage = 100
            states.target_states = []
            db.add(states)

    log.info("demo_language_catalog_opened", languages=len(ALL_PROFILES))


def ensure_reference_data() -> None:
    served = {profile.code for profile in DEFAULT_CATALOG.profiles}

    with session_scope() as db:
        benefit_baselines = ensure_benefit_baselines(db)
        directory_baselines = ensure_directory_baselines(db)
        for profile in DEFAULT_CATALOG.profiles:
            db.merge(
                Language(
                    code=profile.code,
                    name=profile.name,
                    native_name=profile.native_name,
                    stt_provider=profile.stt_provider,
                    stt_locale=profile.resolved_stt_locale(),
                    tts_provider=profile.tts_provider,
                    tts_locale=profile.resolved_tts_locale(),
                    tts_voice_id=profile.tts_voice_id,
                    is_active=True,
                )
            )

        for profile in PLANNED_PROFILES:
            # Do not downgrade a language an operator (or demo bootstrap) already
            # activated; restart would otherwise undo rollout every boot.
            existing = db.get(Language, profile.code)
            db.merge(
                Language(
                    code=profile.code,
                    name=profile.name,
                    native_name=profile.native_name,
                    stt_provider=profile.stt_provider,
                    stt_locale=profile.resolved_stt_locale(),
                    tts_provider=profile.tts_provider,
                    tts_locale=profile.resolved_tts_locale(),
                    tts_voice_id=profile.tts_voice_id,
                    is_active=existing.is_active if existing is not None else False,
                )
            )

        for profile in ALL_PROFILES:
            if db.get(LanguageReadinessReview, profile.code) is None:
                db.add(LanguageReadinessReview(language_code=profile.code))

        for code, name, language_code in DEFAULT_STATES:
            # A state whose language is not yet served is still inserted, but
            # marked inactive: the row documents the expansion path without
            # letting a caller be routed somewhere the agent cannot speak.
            active = language_code in served
            if not active and db.get(Language, language_code) is None:
                db.merge(
                    Language(
                        code=language_code,
                        name=language_code,
                        native_name=language_code,
                        is_active=False,
                    )
                )
            db.merge(
                State(
                    code=code,
                    name=name,
                    primary_language_code=language_code,
                    is_active=active,
                )
            )
        household_fact_definitions = ensure_household_fact_definitions(db)

    ensure_default_feature_flags()

    log.info(
        "reference_data_ready",
        languages=len(DEFAULT_CATALOG.profiles) + len(PLANNED_PROFILES),
        states=len(DEFAULT_STATES),
        active_states=sum(1 for _, _, lang in DEFAULT_STATES if lang in served),
        benefit_baselines=benefit_baselines,
        directory_baselines=directory_baselines,
        household_fact_definitions=household_fact_definitions,
    )
