"""The state machine for one inbound phone call.

    CALL_RECEIVED   -> answer, greet, listen
    CALL_ESTABLISHED-> listen
    SPEECH_CAPTURED -> transcribe, run the agent, speak the reply, listen again
    CALL_FINISHED   -> close the record

Kept apart from the Calls API wrapper so the flow can be tested without HTTP,
and apart from the agent so that a phone call is only a transport. The same
graph, matcher, and escalation serve it as serve the browser; a caller on a
feature phone gets the same eligibility answer as someone on a laptop, which is
the entire premise of the product.

The ceilings — call duration, turn count — are enforced here rather than left
to the provider. A stuck call bills per minute and holds a line someone else
needs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sahaayak_agent.voice import VoiceUnavailable
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.integrations.infobip.calls import (
    MAX_CALL_SECONDS,
    MAX_TURNS,
    InfobipCallsProvider,
    build_calls_provider,
)
from sahaayak_api.rate_limit import RateLimitUnavailable, consume_channel_limit
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import (
    CallSession,
    UserSession,
    channel_identity_hash,
    get_logger,
    new_id,
    session_scope,
    settings,
)

log = get_logger(__name__)

# Spoken when the call is answered, before the caller has said anything. Comes
# from the per-language prompt catalog so it is not a hardcoded English string
# on a Kannada line.
GREETING_KEY = "greeting"

# Said when a turn cannot be understood or the agent produced nothing, so the
# line is never silent — silence on a phone call reads as a dropped call.
FALLBACK_KEY = "didnt_understand"


async def handle_call_event(event: dict) -> None:
    """Process one Calls API event. Never raises; a call must not die on a bug."""
    try:
        await _handle(event)
    except Exception as exc:
        log.error(
            "voice_call_event_failed",
            error=str(exc),
            error_type=exc.__class__.__name__,
            event_type=event.get("type"),
            exc_info=True,
        )


async def _handle(event: dict) -> None:
    provider = build_calls_provider()
    if provider is None:
        log.info("voice_call_ignored", reason="voice_not_configured")
        return

    call_id = str(event.get("call_id") or "")
    if not call_id:
        return

    kind = str(event.get("type") or "").upper()
    if kind == "CALL_RECEIVED":
        await _on_received(provider, call_id, event)
    elif kind == "CALL_ESTABLISHED":
        await _on_established(provider, call_id)
    elif kind in ("SPEECH_CAPTURED", "CALL_CAPTURED_SPEECH"):
        await _on_speech(provider, call_id, event)
    elif kind in ("CALL_FINISHED", "CALL_FAILED", "CALL_HANGUP"):
        _on_finished(call_id, event)


async def _on_received(
    provider: InfobipCallsProvider, call_id: str, event: dict
) -> None:
    caller = str(event.get("from") or "")
    identity = channel_identity_hash("voice", caller)

    with session_scope() as db:
        existing = _find_call(db, call_id)
        if existing is not None:
            # A repeated CALL_RECEIVED is a provider retry, not a second call.
            return
        db.add(
            CallSession(
                id=new_id("call"),
                provider="infobip",
                provider_call_id=call_id,
                hashed_caller_identity=identity,
                language_code=settings.default_language,
                state_code=settings.default_state,
                status="ringing",
            )
        )

    if not await provider.answer(call_id):
        _close(call_id, reason="answer_failed")
        return

    with session_scope() as db:
        row = _find_call(db, call_id)
        if row is not None:
            row.status = "answered"
            row.answered_at = datetime.now(UTC)
            db.add(row)

    await _speak_catalog(provider, call_id, GREETING_KEY)
    await provider.capture_speech(call_id, language=settings.default_language)


async def _on_established(provider: InfobipCallsProvider, call_id: str) -> None:
    with session_scope() as db:
        row = _find_call(db, call_id)
        if row is None:
            return
        row.status = "in_progress"
        db.add(row)
        language = row.language_code
    await provider.capture_speech(call_id, language=language)


async def _on_speech(
    provider: InfobipCallsProvider, call_id: str, event: dict
) -> None:
    with session_scope() as db:
        row = _find_call(db, call_id)
        if row is None:
            return
        identity = row.hashed_caller_identity
        language = row.language_code
        turn_count = row.turn_count
        started_at = _as_utc(row.started_at)

    # Event callbacks do not have a browser IP or guest token. Use the
    # provider-asserted caller identity only after it has been HMAC-derived and
    # stored as a hash, and apply both short-window and daily ceilings before
    # transcription or agent work can spend provider budget.
    try:
        burst = await consume_channel_limit(
            identity,
            bucket="telephony_inbound",
            limit=settings.rate_limit_telephony_inbound_per_caller,
            window_seconds=60,
        )
        daily = await consume_channel_limit(
            identity,
            bucket="telephony_inbound_daily",
            limit=settings.rate_limit_telephony_inbound_per_caller_per_day,
            window_seconds=86_400,
        )
    except RateLimitUnavailable:
        log.error("voice_call_rate_limiter_unavailable", identity=identity[:12])
        await _end(provider, call_id, reason="rate_limiter_unavailable")
        return
    if not burst.allowed or not daily.allowed:
        log.warning("voice_call_rate_limited", identity=identity[:12], call_id=call_id)
        await _end(provider, call_id, reason="caller_rate_limited")
        return

    now = datetime.now(UTC)
    if (now - started_at).total_seconds() > MAX_CALL_SECONDS:
        await _end(provider, call_id, reason="max_duration")
        return
    if turn_count >= MAX_TURNS:
        # Long past the point where a person would serve the caller better.
        await _end(provider, call_id, reason="max_turns")
        return

    transcript = await _transcript_from(event, language=language)
    if not transcript:
        await _speak_catalog(provider, call_id, FALLBACK_KEY, language=language)
        await provider.capture_speech(call_id, language=language)
        return

    caller_id = _ensure_call_session(identity)
    runtime = get_runtime()
    session, state = await runtime.run_turn(
        caller_id=caller_id, transcript=transcript, language_code=language
    )

    with session_scope() as db:
        row = _find_call(db, call_id)
        if row is not None:
            row.turn_count += 1
            row.session_id = session.id
            row.language_code = session.language_code
            row.state_code = session.state_code
            db.add(row)

    record_telemetry(
        event_type="turn",
        route="voice/call",
        method="CALL",
        surface="voice",
        language_code=session.language_code,
        state_code=session.state_code,
        provider="infobip",
        outcome="escalated" if state.needs_escalation else "success",
        safe_metadata={"turn_index": state.turn_index, "matches": len(state.matches)},
    )

    await _speak(provider, call_id, state.response_text, language=session.language_code)

    if state.needs_escalation and not state.pending_slot:
        # The offer has been read out; continuing to interrogate someone who
        # already needs a human wastes their airtime.
        await _end(provider, call_id, reason="escalated")
        return

    await provider.capture_speech(call_id, language=session.language_code)


def _on_finished(call_id: str, event: dict) -> None:
    _close(
        call_id,
        reason=str(event.get("reason") or "completed"),
        error_code=str(event.get("error_code") or ""),
    )


async def _transcript_from(event: dict, *, language: str) -> str:
    """Text for this turn, from the provider's own capture or our Whisper pass.

    Provider-side speech recognition is used when it supplies one, because it
    saves an audio round trip on a live call. Whisper is the fallback, and the
    audio is discarded either way — no recording is kept.
    """
    provider_text = str(event.get("text") or "").strip()
    if provider_text:
        return provider_text[:2000]

    audio = event.get("audio")
    if not isinstance(audio, bytes) or not audio:
        return ""

    voice = get_voice()
    if not voice.stt_available:
        return ""
    try:
        result = await voice.transcribe(audio, language_code=language, filename="turn.wav")
    except (VoiceUnavailable, Exception) as exc:  # noqa: B014 - VoiceUnavailable is explicit
        log.warning("call_transcription_failed", error=exc.__class__.__name__)
        return ""
    return result.text.strip()[:2000]


async def _speak_catalog(
    provider: InfobipCallsProvider, call_id: str, key: str, *, language: str | None = None
) -> None:
    from sahaayak_agent.prompts import get_catalog

    catalog = get_catalog(language or settings.default_language)
    await _speak(provider, call_id, catalog.render(key), language=language)


async def _speak(
    provider: InfobipCallsProvider, call_id: str, text: str, *, language: str | None = None
) -> None:
    """Synthesize and play one utterance.

    A synthesis failure is not allowed to end the call silently; the caller
    hears nothing for that turn but the line stays open and the next capture
    still happens.
    """
    if not text.strip():
        return

    voice = get_voice()
    if not voice.tts_available:
        log.info("call_speech_skipped", reason="tts_unavailable")
        return

    try:
        spoken = await voice.speak(text, language_code=language or settings.default_language)
    except Exception as exc:
        log.warning("call_synthesis_failed", error=exc.__class__.__name__)
        return

    if not spoken.audio:
        return
    file_id = await provider.upload_audio(spoken.audio, mime_type=spoken.mime_type)
    if not file_id:
        return
    await provider.play_file(call_id, file_id)


async def _end(provider: InfobipCallsProvider, call_id: str, *, reason: str) -> None:
    await provider.hangup(call_id, reason=reason)
    _close(call_id, reason=reason)


def _close(call_id: str, *, reason: str, error_code: str = "") -> None:
    with session_scope() as db:
        row = _find_call(db, call_id)
        if row is None or row.ended_at is not None:
            return
        now = datetime.now(UTC)
        row.status = "ended"
        row.ended_at = now
        row.end_reason = reason
        row.provider_error_code = error_code
        row.duration_seconds = int((now - _as_utc(row.started_at)).total_seconds())
        db.add(row)
    log.info("voice_call_ended", reason=reason)


def _ensure_call_session(identity: str) -> str:
    """Conversation session for a hashed caller identity.

    ``auth_mode="telephony"`` so it cannot satisfy the browser dependency,
    which requires ``guest``. A caller ID is asserted by the network and is not
    proof of anything.
    """
    with session_scope() as db:
        existing = db.query(UserSession).filter_by(phone_or_session_id=identity).first()
        if existing is None:
            db.add(
                UserSession(
                    id=new_id("ses"),
                    phone_or_session_id=identity,
                    auth_mode="telephony",
                    state_code=settings.default_state,
                    language_code=settings.default_language,
                )
            )
    return identity


def _find_call(db, call_id: str) -> CallSession | None:
    return (
        db.query(CallSession)
        .filter_by(provider="infobip", provider_call_id=call_id)
        .first()
    )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
