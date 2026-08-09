"""Reference data the app needs before it can serve a single call.

Languages and states are configuration expressed as rows, so they are ensured
idempotently at startup rather than left to a migration someone has to remember
to run. Benefits are not seeded here — those come from the ingestion pipeline,
and inventing them would undercut the whole point of using real myScheme data.
"""

from __future__ import annotations

from sahaayak_agent.languages import ALL_PROFILES, DEFAULT_CATALOG, DEFAULT_STATES, PLANNED_PROFILES
from sahaayak_common import (
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
                    is_active=False,
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
