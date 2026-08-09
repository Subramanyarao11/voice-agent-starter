"""Browser voice transport with editable transcripts and streamed audio.

Modern browsers send small 24 kHz PCM frames. When the opt-in OpenAI Realtime
transcription bridge is enabled, those frames are forwarded incrementally and
partial transcript deltas are surfaced to the browser. The default path still
accepts MediaRecorder containers and batch-transcribes the completed utterance,
so an unconfigured realtime provider never breaks voice fallback. In both paths
the caller reviews or edits the transcript before the reasoning graph runs.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import wave
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from sahaayak_agent import AgentRuntime, to_response
from sahaayak_agent.voice import VoiceService, VoiceUnavailable
from sahaayak_api.browser_auth import principal_for_access_token
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.rate_limit import enforce_rate_limit, enforce_request_limits
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import feature_flag_enabled, get_logger, get_session, settings

log = get_logger(__name__)

router = APIRouter(tags=["conversation"])

MAX_STREAM_AUDIO_BYTES = 10 * 1024 * 1024
MAX_STREAM_CHUNKS = 480
TRANSCRIPT_REVIEW_SECONDS = 120


class StreamStart(BaseModel):
    type: str = "start"
    access_token: str = Field(min_length=16, max_length=256)
    language_code: str | None = Field(default=None, max_length=16)
    state_code: str | None = Field(default=None, max_length=16)
    mime_type: str | None = Field(default=None, max_length=80)
    audio_format: Literal["container", "pcm16"] = "container"
    sample_rate: int = Field(default=24_000, ge=8_000, le=48_000)
    speak: bool = True


class TranscriptSubmission(BaseModel):
    type: Literal["submit_transcript"]
    text: str = Field(min_length=1, max_length=2_000)


@router.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    """Handle one or more browser voice turns on a server-owned socket."""
    await websocket.accept()
    db_dependency = get_session()
    db_session = next(db_dependency)
    processing: asyncio.Task[None] | None = None
    transcript_future: asyncio.Future[str | None] | None = None
    realtime_session: Any = None
    try:
        start = await _receive_start(websocket)
        if start is None:
            return

        # A WebSocket is an expensive long-lived resource. Limit handshakes
        # before resolving the bearer token so unauthenticated socket floods do
        # not consume database or provider work.
        try:
            await enforce_rate_limit(
                websocket,
                session_id=None,
                bucket="voice_socket",
            )
        except Exception as exc:
            await _send_error(websocket, "rate_limited", _rate_limit_message(exc))
            await websocket.close(code=1013)
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
        if not feature_flag_enabled(
            "voice_streaming",
            subject=principal.session_id,
            language_code=language_code,
            state_code=state_code,
        ):
            await _send_error(
                websocket,
                "voice_streaming_disabled",
                "Streaming voice is not available for this rollout cohort yet.",
            )
            await websocket.close(code=1013)
            return
        if start.audio_format == "pcm16" and start.sample_rate != 24_000:
            await _send_error(
                websocket,
                "unsupported_audio_format",
                "PCM streaming must use a 24 kHz sample rate.",
            )
            await websocket.close(code=1003)
            return
        speak = start.speak
        chunks: list[bytes] = []
        total_bytes = 0
        completed_turns = 0
        connection_deadline = asyncio.get_running_loop().time() + max(
            30, settings.voice_stream_max_seconds
        )

        if start.audio_format == "pcm16" and isinstance(voice, VoiceService):
            try:
                realtime_session = await voice.start_realtime_transcription(
                    language_code=language_code,
                    subject=principal.session_id,
                    state_code=state_code,
                    on_delta=lambda delta: _send_transcript_delta(websocket, delta),
                )
            except VoiceUnavailable:
                # PCM can still be wrapped as a WAV for the batch provider. The
                # browser does not need to know which provider path is active.
                realtime_session = None
                await websocket.send_json(
                    {
                        "type": "stream_notice",
                        "code": "realtime_stt_fallback",
                        "message": (
                            "Realtime transcription is unavailable; using the "
                            "buffered voice fallback."
                        ),
                    }
                )

        await websocket.send_json(
            {
                "type": "ready",
                "session_id": principal.session_id,
                "audio_format": start.audio_format,
                "realtime_stt": realtime_session is not None,
            }
        )
        while True:
            remaining_connection = connection_deadline - asyncio.get_running_loop().time()
            if remaining_connection <= 0:
                await _send_error(
                    websocket,
                    "voice_connection_expired",
                    "This voice connection has reached its safety time limit.",
                )
                await websocket.close(code=1000)
                return
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=min(settings.voice_stream_idle_timeout_seconds, remaining_connection),
                )
            except TimeoutError:
                await _send_error(
                    websocket,
                    "voice_connection_idle",
                    "The voice connection was idle for too long. Please start again.",
                )
                await websocket.close(code=1000)
                return
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
                    (start.audio_format == "container" and len(chunks) >= MAX_STREAM_CHUNKS)
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
                if realtime_session is not None:
                    await realtime_session.append(binary)
                else:
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
                if completed_turns >= settings.voice_stream_max_turns_per_socket:
                    await _send_error(
                        websocket,
                        "voice_turn_limit",
                        "Please start a new voice connection for more turns.",
                    )
                    await websocket.close(code=1000)
                    return
                if total_bytes <= 0:
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
                    await enforce_request_limits(
                        websocket,
                        session_id=principal.session_id,
                        bucket="voice",
                    )
                except Exception as exc:
                    await _send_error(websocket, "rate_limited", _rate_limit_message(exc))
                    chunks.clear()
                    total_bytes = 0
                    continue
                audio = (
                    b""
                    if realtime_session is not None
                    else _pcm16_to_wav(b"".join(chunks), start.sample_rate)
                    if start.audio_format == "pcm16"
                    else b"".join(chunks)
                )
                chunks.clear()
                total_bytes = 0
                transcript_future = asyncio.get_running_loop().create_future()
                processing = asyncio.create_task(
                    _process_turn(
                        websocket,
                        runtime=runtime,
                        voice=voice,
                        caller_id=principal.caller_id,
                        language_code=language_code,
                        state_code=state_code,
                        audio=audio,
                        realtime_session=realtime_session,
                        transcript_future=transcript_future,
                        speak=speak,
                        filename=(
                            "sahaayak-stream.ogg"
                            if "ogg" in (start.mime_type or "")
                            else "sahaayak-stream.webm"
                        ),
                    )
                )
                completed_turns += 1
                continue

            if event_type in {"interrupt", "cancel"}:
                if transcript_future is not None and not transcript_future.done():
                    transcript_future.set_result(None)
                if processing is not None and not processing.done():
                    processing.cancel()
                    try:
                        await processing
                    except asyncio.CancelledError:
                        pass
                processing = None
                chunks.clear()
                total_bytes = 0
                if realtime_session is not None:
                    await realtime_session.cancel()
                    realtime_session = None
                await websocket.send_json({"type": "interrupted"})
                continue

            if event_type == "submit_transcript":
                if transcript_future is None or transcript_future.done():
                    await _send_error(
                        websocket,
                        "transcript_not_editable",
                        "There is no voice transcript waiting for review.",
                    )
                    continue
                try:
                    submission = TranscriptSubmission.model_validate(event)
                except ValidationError:
                    await _send_error(
                        websocket,
                        "invalid_transcript",
                        "Please provide a transcript between 1 and 2,000 characters.",
                    )
                    continue
                cleaned_text = submission.text.strip()
                if not cleaned_text:
                    await _send_error(
                        websocket,
                        "invalid_transcript",
                        "Please provide a transcript between 1 and 2,000 characters.",
                    )
                    continue
                transcript_future.set_result(cleaned_text)
                continue

            if event_type == "cancel_transcript":
                if transcript_future is not None and not transcript_future.done():
                    transcript_future.set_result(None)
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
        if transcript_future is not None and not transcript_future.done():
            transcript_future.set_result(None)
        if realtime_session is not None:
            await realtime_session.close()
        db_dependency.close()
        db_session.close()


async def _receive_start(websocket: WebSocket) -> StreamStart | None:
    try:
        # Microphone permission prompts can legitimately take longer than ten
        # seconds, especially on mobile browsers. Keep the socket bounded
        # while still giving the caller time to approve the device prompt.
        message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
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
    realtime_session: Any,
    transcript_future: asyncio.Future[str | None],
    speak: bool,
    filename: str,
) -> None:
    try:
        if realtime_session is not None:
            transcription = await realtime_session.finish()
        else:
            transcription = await _transcribe_for_session(
                voice,
                audio,
                language_code=language_code,
                state_code=state_code,
                session_id=caller_id,
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

    original_transcript = transcription.text.strip()
    if not original_transcript:
        await _send_error(
            websocket,
            "empty_transcript",
            "I could not make out any words. Please try speaking again.",
        )
        return

    await websocket.send_json(
        {
            "type": "transcript",
            "text": original_transcript,
            "provider": transcription.provider,
            "editable": True,
        }
    )
    try:
        final_transcript = await asyncio.wait_for(
            asyncio.shield(transcript_future),
            timeout=TRANSCRIPT_REVIEW_SECONDS,
        )
    except TimeoutError:
        await _send_error(
            websocket,
            "transcript_review_timeout",
            "The transcript review timed out. Please record that question again.",
        )
        return
    if final_transcript is None:
        await websocket.send_json({"type": "transcript_cancelled"})
        await websocket.send_json({"type": "turn_end", "tts_chunks": 0, "cancelled": True})
        return

    final_transcript = final_transcript.strip()
    transcript_edited = final_transcript != original_transcript
    await websocket.send_json(
        {
            "type": "transcript_accepted",
            "text": final_transcript,
            "edited": transcript_edited,
        }
    )
    session, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript=final_transcript,
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
                spoken = await _speak_for_session(
                    voice,
                    sentence,
                    language_code=language_code,
                    state_code=state_code,
                    session_id=caller_id,
                )
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
            "transcript_edited": transcript_edited,
            "transcript_characters": len(final_transcript),
        },
    )
    await websocket.send_json(
        {
            "type": "turn_end",
            "tts_chunks": tts_chunks,
            "transcript_edited": transcript_edited,
        }
    )


async def _transcribe_for_session(
    voice: VoiceService,
    audio: bytes,
    *,
    language_code: str,
    state_code: str,
    session_id: str,
    filename: str,
):
    if isinstance(voice, VoiceService):
        return await voice.transcribe(
            audio,
            language_code=language_code,
            filename=filename,
            subject=session_id,
            state_code=state_code,
        )
    return await voice.transcribe(audio, language_code=language_code, filename=filename)


async def _speak_for_session(
    voice: VoiceService,
    text: str,
    *,
    language_code: str,
    state_code: str,
    session_id: str,
):
    if isinstance(voice, VoiceService):
        return await voice.speak(
            text,
            language_code=language_code,
            subject=session_id,
            state_code=state_code,
        )
    return await voice.speak(text, language_code=language_code)


async def _send_transcript_delta(websocket: WebSocket, delta: str) -> None:
    try:
        await websocket.send_json({"type": "transcript_delta", "text": delta})
    except Exception:
        pass


def _pcm16_to_wav(audio: bytes, sample_rate: int) -> bytes:
    """Wrap streamed mono PCM in a valid container for batch STT fallback."""
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(audio)
    return output.getvalue()


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
