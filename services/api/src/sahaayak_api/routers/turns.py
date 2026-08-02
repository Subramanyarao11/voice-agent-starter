"""The conversation endpoints: one for text, one for audio.

Both funnel into the same runtime. The voice route only adds transcription
before and synthesis after, which is what keeps the browser demo and a
telephony webhook exercising identical logic rather than drifting apart.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from sahaayak_agent import AgentRuntime, to_response
from sahaayak_agent.voice import VoiceService, VoiceUnavailable
from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import get_logger
from sahaayak_contracts import TurnRequest, TurnResponse

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["conversation"])

# Roughly a minute of speech. Beyond this something is wrong with the client,
# and transcribing it would be slow and expensive.
MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/turns", response_model=TurnResponse)
async def take_text_turn(
    payload: TurnRequest,
    request: Request,
    http_response: Response,
    runtime: AgentRuntime = Depends(get_runtime),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> TurnResponse:
    """One text turn. The fastest way to exercise the dialogue during a build."""
    decision = await enforce_rate_limit(request, session_id=principal.session_id, bucket="text")
    apply_rate_limit_headers(http_response, decision)
    session, state = await runtime.run_turn(
        caller_id=principal.caller_id,
        transcript=payload.text,
        language_code=payload.language_code or principal.language_code,
        state_code=payload.state_code or principal.state_code,
    )
    response = to_response(session, state)
    record_telemetry(
        event_type="turn",
        route="/api/turns",
        method="POST",
        surface="text",
        language_code=session.language_code,
        state_code=session.state_code,
        outcome=_turn_outcome(state),
        safe_metadata=_turn_metadata(state),
    )
    return response


@router.post("/voice/turns", response_model=TurnResponse)
async def take_voice_turn(
    request: Request,
    http_response: Response,
    audio: UploadFile = File(...),
    language_code: str | None = Form(None),
    state_code: str | None = Form(None),
    speak: bool = Form(True),
    runtime: AgentRuntime = Depends(get_runtime),
    voice: VoiceService = Depends(get_voice),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> TurnResponse:
    """Audio in, audio out. Shared by the browser demo and any telephony webhook."""
    decision = await enforce_rate_limit(request, session_id=principal.session_id, bucket="voice")
    apply_rate_limit_headers(http_response, decision)
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large")

    language = language_code or principal.language_code

    try:
        transcription = await voice.transcribe(
            audio_bytes,
            language_code=language,
            filename=audio.filename or "audio.wav",
        )
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    session, state = await runtime.run_turn(
        caller_id=principal.caller_id,
        transcript=transcription.text,
        language_code=language,
        state_code=state_code or principal.state_code,
    )
    response = to_response(session, state)

    # Text is returned either way. A synthesis failure should degrade the call
    # to on-screen text, not lose the answer the agent already worked out.
    tts_provider = None
    tts_cache_hit = False
    tts_billed_characters = 0
    if speak and state.response_text and voice.tts_available:
        try:
            spoken = await voice.speak(state.response_text, language_code=language)
            if spoken.audio:
                response.audio_base64 = base64.b64encode(spoken.audio).decode("ascii")
                response.audio_mime_type = spoken.mime_type
                tts_provider = spoken.provider
                tts_cache_hit = spoken.cached
                tts_billed_characters = spoken.billed_characters
        except Exception as exc:
            log.warning("synthesis_failed_returning_text_only", error=str(exc))

    record_telemetry(
        event_type="turn",
        route="/api/voice/turns",
        method="POST",
        surface="voice",
        language_code=session.language_code,
        state_code=session.state_code,
        provider=transcription.provider,
        outcome=_turn_outcome(state),
        safe_metadata={
            **_turn_metadata(state),
            "tts_provider": tts_provider or "none",
            "tts_cache_hit": tts_cache_hit,
            "tts_billed_characters": tts_billed_characters,
        },
    )
    return response


def _turn_outcome(state) -> str:
    if state.needs_escalation:
        return "escalated"
    if state.pending_slot:
        return "follow_up"
    if not state.matches and not state.knowledge_answer:
        return "no_match"
    return "success"


def _turn_metadata(state) -> dict[str, int | str]:
    return {
        "intent": state.intent.value,
        "match_count": len(state.matches),
        "source_count": len(state.knowledge_sources),
    }
