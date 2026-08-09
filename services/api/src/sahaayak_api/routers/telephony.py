"""Provider-neutral signed telephony webhook seam.

The adapter deliberately accepts audio and returns the same response contract
as the browser voice route. A real provider integration can translate its
call-control payload into this small contract without duplicating the agent
graph. The endpoint stays disabled until a webhook secret is configured.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlmodel import Session

from sahaayak_agent import AgentRuntime, to_response
from sahaayak_agent.voice import VoiceService, VoiceUnavailable
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_request_limits
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import UserSession, get_logger, get_session, settings
from sahaayak_contracts import TurnResponse

log = get_logger(__name__)
router = APIRouter(prefix="/api/telephony", tags=["telephony"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/turns", response_model=TurnResponse)
async def take_telephony_turn(
    request: Request,
    http_response: Response,
    audio: UploadFile = File(...),
    caller_id: str = Form(..., min_length=1, max_length=256),
    language_code: str | None = Form(None),
    state_code: str | None = Form(None),
    speak: bool = Form(True),
    db: Session = Depends(get_session),
    runtime: AgentRuntime = Depends(get_runtime),
    voice: VoiceService = Depends(get_voice),
) -> TurnResponse:
    _require_enabled()
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large")
    _verify_signature(request, caller_id.strip(), audio_bytes)

    identity = _telephony_identity(caller_id.strip())
    session = runtime.get_or_create_session(
        identity,
        language_code=language_code or settings.default_language,
        state_code=state_code or settings.default_state,
    )
    _mark_telephony_session(db, session.id)
    decision = await enforce_request_limits(request, session_id=session.id, bucket="voice")
    apply_rate_limit_headers(http_response, decision)
    session, state = await runtime.run_turn(
        caller_id=identity,
        transcript=await _transcribe(
            voice,
            audio_bytes,
            language_code or settings.default_language,
            audio.filename,
        ),
        language_code=language_code or settings.default_language,
        state_code=state_code or settings.default_state,
    )

    response = to_response(session, state)
    tts_provider = None
    tts_cache_hit = False
    if speak and state.response_text and voice.tts_available:
        try:
            spoken = await voice.speak(
                state.response_text,
                language_code=language_code or settings.default_language,
            )
            if spoken.audio:
                response.audio_base64 = base64.b64encode(spoken.audio).decode("ascii")
                response.audio_mime_type = spoken.mime_type
                tts_provider = spoken.provider
                tts_cache_hit = spoken.cached
        except Exception as exc:  # pragma: no cover - provider failure path
            log.warning("telephony_synthesis_failed_returning_text", error=exc.__class__.__name__)

    record_telemetry(
        event_type="turn",
        route="/api/telephony/turns",
        method="POST",
        surface="telephony",
        language_code=session.language_code,
        state_code=session.state_code,
        provider="telephony",
        outcome="escalated" if state.needs_escalation else "success",
        safe_metadata={"tts_provider": tts_provider or "none", "tts_cache_hit": tts_cache_hit},
    )
    return response


async def _transcribe(
    voice: VoiceService, audio: bytes, language_code: str, filename: str | None
) -> str:
    try:
        result = await voice.transcribe(
            audio,
            language_code=language_code,
            filename=filename or "telephony.wav",
        )
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.text


def _require_enabled() -> None:
    if not settings.telephony_enabled or not settings.telephony_webhook_secret.strip():
        raise HTTPException(status_code=404, detail="Telephony integration is not enabled")


def _verify_signature(request: Request, caller_id: str, audio: bytes) -> None:
    timestamp = request.headers.get("X-Telephony-Timestamp", "").strip()
    supplied = request.headers.get("X-Telephony-Signature", "").strip()
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Telephony signature is invalid") from exc
    if abs(time.time() - timestamp_value) > max(30, settings.telephony_max_timestamp_skew_seconds):
        raise HTTPException(status_code=401, detail="Telephony signature has expired")

    audio_hash = hashlib.sha256(audio).hexdigest()
    message = f"{timestamp}.{caller_id}.{audio_hash}".encode()
    expected = "sha256=" + hmac.new(
        settings.telephony_webhook_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Telephony signature is invalid")


def _telephony_identity(caller_id: str) -> str:
    digest = hmac.new(
        settings.telephony_webhook_secret.encode("utf-8"),
        caller_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"telephony:{settings.telephony_provider}:{digest}"


def _mark_telephony_session(db: Session, session_id: str) -> None:
    row = db.get(UserSession, session_id)
    if row is None:
        return
    row.auth_mode = "telephony"
    row.access_token_hash = None
    row.expires_at = None
    db.add(row)
    db.commit()
