"""Chunked browser voice transport with sentence-level response audio.

The browser sends short MediaRecorder chunks over a WebSocket and uses local
voice-activity detection to decide when an utterance ends. OpenAI Whisper still
needs a complete utterance today, so the server buffers only the current turn,
transcribes it once, and starts Sarvam synthesis one sentence at a time. This
reduces time-to-first-audio without pretending that the current STT provider is
incremental.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from sahaayak_agent import AgentRuntime, to_response
from sahaayak_agent.voice import VoiceService, VoiceUnavailable
from sahaayak_api.browser_auth import principal_for_access_token
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.rate_limit import enforce_rate_limit
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import get_logger, get_session

log = get_logger(__name__)

router = APIRouter(tags=["conversation"])

MAX_STREAM_AUDIO_BYTES = 10 * 1024 * 1024
MAX_STREAM_CHUNKS = 480
MAX_STREAM_SECONDS = 90


class StreamStart(BaseModel):
    type: str = "start"
    access_token: str = Field(min_length=16, max_length=256)
    language_code: str | None = Field(default=None, max_length=16)
    state_code: str | None = Field(default=None, max_length=16)
    mime_type: str | None = Field(default=None, max_length=80)
    speak: bool = True


@router.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    """Handle one or more browser voice turns on a server-owned socket."""
    await websocket.accept()
    db_dependency = get_session()
    db_session = next(db_dependency)
    processing: asyncio.Task[None] | None = None
    try:
        start = await _receive_start(websocket)
        if start is None:
            return

        principal = principal_for_access_token(db_session, start.access_token)
        if principal is None:
            await _send_error(websocket, "unauthorized", "Your guest session has expired.")
            await websocket.close(code=1008)
            return

        runtime = get_runtime()
        voice = get_voice()
        language_code = (start.language_code or principal.language_code).strip()[:16]
        state_code = (start.state_code or principal.state_code).strip()[:16]
        speak = start.speak
        chunks: list[bytes] = []
        total_bytes = 0

        await websocket.send_json({"type": "ready", "session_id": principal.session_id})
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            binary = message.get("bytes")
            if binary is not None:
                if processing is not None and not processing.done():
                    # The client must interrupt before starting a new utterance.
                    await _send_error(
                        websocket,
                        "interrupt_required",
                        "Interrupt the reply before speaking again.",
                    )
                    continue
                if (
                    len(chunks) >= MAX_STREAM_CHUNKS
                    or total_bytes + len(binary) > MAX_STREAM_AUDIO_BYTES
                ):
                    await _send_error(
                        websocket,
                        "audio_too_large",
                        "That voice turn is too long. Please try again.",
                    )
                    chunks.clear()
                    total_bytes = 0
                    continue
                chunks.append(binary)
                total_bytes += len(binary)
                continue

            text = message.get("text") or ""
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                await _send_error(
                    websocket,
                    "invalid_event",
                    "The voice connection sent an invalid event.",
                )
                continue
            if not isinstance(event, dict):
                await _send_error(
                    websocket,
                    "invalid_event",
                    "The voice connection sent an invalid event.",
                )
                continue

            event_type = event.get("type")
            if event_type == "end_turn":
                if not chunks:
                    await _send_error(
                        websocket,
                        "empty_audio",
                        "I did not hear anything. Please try again.",
                    )
                    continue
                if processing is not None and not processing.done():
                    await _send_error(
                        websocket,
                        "turn_in_progress",
                        "The previous voice turn is still processing.",
                    )
                    continue
                try:
                    await enforce_rate_limit(
                        websocket,
                        session_id=principal.session_id,
                        bucket="voice",
                    )
                except Exception as exc:
                    await _send_error(websocket, "rate_limited", _rate_limit_message(exc))
                    chunks.clear()
                    total_bytes = 0
                    continue
                audio = b"".join(chunks)
                chunks.clear()
                total_bytes = 0
                processing = asyncio.create_task(
                    _process_turn(
                        websocket,
                        runtime=runtime,
                        voice=voice,
                        caller_id=principal.caller_id,
                        language_code=language_code,
                        state_code=state_code,
                        audio=audio,
                        speak=speak,
                        filename=(
                            "sahaayak-stream.ogg"
                            if "ogg" in (start.mime_type or "")
                            else "sahaayak-stream.webm"
                        ),
                    )
                )
                continue

            if event_type in {"interrupt", "cancel"}:
                if processing is not None and not processing.done():
                    processing.cancel()
                    try:
                        await processing
                    except asyncio.CancelledError:
                        pass
                processing = None
                chunks.clear()
                total_bytes = 0
                await websocket.send_json({"type": "interrupted"})
                continue

            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            await _send_error(
                websocket,
                "unknown_event",
                "The voice connection sent an unknown event.",
            )
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - transport failures vary by server
        log.warning("voice_stream_failed", error=exc.__class__.__name__)
    finally:
        if processing is not None and not processing.done():
            processing.cancel()
        db_dependency.close()
        db_session.close()


async def _receive_start(websocket: WebSocket) -> StreamStart | None:
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        return StreamStart.model_validate(message)
    except (TimeoutError, ValidationError, WebSocketDisconnect):
        await _send_error(
            websocket,
            "invalid_start",
            "The voice connection could not be started.",
        )
        await websocket.close(code=1008)
        return None


async def _process_turn(
    websocket: WebSocket,
    *,
    runtime: AgentRuntime,
    voice: VoiceService,
    caller_id: str,
    language_code: str,
    state_code: str,
    audio: bytes,
    speak: bool,
    filename: str,
) -> None:
    try:
        transcription = await voice.transcribe(
            audio,
            language_code=language_code,
            filename=filename,
        )
    except VoiceUnavailable:
        await _send_error(
            websocket,
            "voice_unavailable",
            "Voice input is temporarily unavailable. Text chat is still available.",
        )
        return
    except Exception as exc:
        log.warning("voice_stream_transcription_failed", error=exc.__class__.__name__)
        await _send_error(
            websocket,
            "transcription_failed",
            "I could not understand that recording. Please try again.",
        )
        return

    await websocket.send_json({
        "type": "transcript",
        "text": transcription.text,
        "provider": transcription.provider,
    })
    session, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript=transcription.text,
        language_code=language_code,
        state_code=state_code,
    )
    response = to_response(session, state)
    response_payload = response.model_dump(mode="json")
    await websocket.send_json({"type": "turn", "turn": response_payload})

    tts_provider = "none"
    tts_cache_hits = 0
    tts_chunks = 0
    if speak and response.response_text and voice.tts_available:
        for index, sentence in enumerate(_sentence_chunks(response.response_text)):
            try:
                spoken = await voice.speak(sentence, language_code=language_code)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # text response remains available
                log.warning("voice_stream_synthesis_failed", error=exc.__class__.__name__)
                await websocket.send_json({"type": "tts_error", "index": index})
                continue
            if not spoken.audio:
                continue
            tts_provider = spoken.provider
            tts_cache_hits += int(spoken.cached)
            tts_chunks += 1
            await websocket.send_json({
                "type": "audio_chunk",
                "index": index,
                "mime_type": spoken.mime_type,
                "audio_base64": base64.b64encode(spoken.audio).decode("ascii"),
            })

    record_telemetry(
        event_type="turn",
        route="/api/voice/stream",
        method="WEBSOCKET",
        surface="voice",
        language_code=session.language_code,
        state_code=session.state_code,
        provider=transcription.provider,
        outcome=_turn_outcome(state),
        safe_metadata={
            "intent": state.intent.value,
            "match_count": len(state.matches),
            "source_count": len(state.knowledge_sources),
            "tts_provider": tts_provider,
            "tts_chunks": tts_chunks,
            "tts_cache_hits": tts_cache_hits,
        },
    )
    await websocket.send_json({"type": "turn_end", "tts_chunks": tts_chunks})


def _sentence_chunks(text: str, *, max_characters: int = 240) -> list[str]:
    """Split for first-audio latency while keeping chunks speakable."""
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?।॥])\s+", text.strip())
        if part.strip()
    ]
    chunks: list[str] = []
    for sentence in sentences or [text.strip()]:
        while len(sentence) > max_characters:
            split_at = sentence.rfind(" ", 0, max_characters)
            split_at = split_at if split_at > 40 else max_characters
            chunks.append(sentence[:split_at].strip())
            sentence = sentence[split_at:].strip()
        if sentence:
            chunks.append(sentence)
    return chunks


def _turn_outcome(state: Any) -> str:
    if state.needs_escalation:
        return "escalated"
    if state.pending_slot:
        return "follow_up"
    if not state.matches and not state.knowledge_answer:
        return "no_match"
    return "success"


def _rate_limit_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", "")
    return str(detail) if detail else "Voice is temporarily rate-limited. Please try again shortly."


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    try:
        await websocket.send_json({"type": "error", "code": code, "message": message})
    except Exception:
        pass
