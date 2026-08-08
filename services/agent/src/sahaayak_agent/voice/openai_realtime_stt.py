"""Opt-in OpenAI Realtime transcription for PCM browser streams.

The normal browser voice path remains batch Whisper-compatible. This adapter is
used only when ``OPENAI_REALTIME_STT_ENABLED=true`` and the caller sends
24 kHz mono PCM frames. It transcribes audio incrementally, but does not run
the Sahaayak reasoning graph until the caller accepts or edits the transcript.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable

from sahaayak_agent.tracing import start_span
from sahaayak_agent.voice.base import VoiceUnavailable
from sahaayak_common import (
    BudgetError,
    BudgetReservation,
    OpenAIBudgetLedger,
    get_logger,
    settings,
)
from sahaayak_contracts import LanguageProfile, TranscriptionResult

log = get_logger(__name__)

TranscriptDeltaHandler = Callable[[str], Awaitable[None]]


class OpenAIRealtimeTranscriptionSession:
    """One cancellable provider session shared by one browser voice turn."""

    def __init__(
        self,
        *,
        client: object,
        connection: object,
        reservation: BudgetReservation,
        profile: LanguageProfile,
        model: str,
        on_delta: TranscriptDeltaHandler | None,
    ) -> None:
        self._client = client
        self._connection = connection
        self._reservation = reservation
        self._profile = profile
        self._model = model
        self._on_delta = on_delta
        self._transcript_parts: list[str] = []
        self._completed: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._reader = asyncio.create_task(self._read_events())
        self._closed = False
        self._budget_finalized = False

    async def append(self, audio: bytes) -> None:
        """Forward one little-endian PCM16 frame without buffering it locally."""
        if self._closed:
            raise VoiceUnavailable("the realtime speech session is closed")
        encoded = base64.b64encode(audio).decode("ascii")
        await self._connection.input_audio_buffer.append(audio=encoded)

    async def finish(self) -> TranscriptionResult:
        """Commit the remote buffer and wait for the completed transcript."""
        if self._closed:
            raise VoiceUnavailable("the realtime speech session is closed")
        try:
            await self._connection.input_audio_buffer.commit()
            text = await asyncio.wait_for(asyncio.shield(self._completed), timeout=30)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._record_failure(exc)
            await self.close()
            raise VoiceUnavailable("realtime speech-to-text failed") from exc

        self._record_completion()
        await self.close()
        return TranscriptionResult(
            text=text.strip(),
            language_code=self._profile.code,
            provider="openai_realtime_transcribe",
        )

    async def cancel(self) -> None:
        """Cancel without turning a partial transcript into a conversation turn."""
        if self._closed:
            return
        try:
            await self._connection.input_audio_buffer.clear()
        except Exception:
            pass
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._budget_finalized:
            self._record_failure(VoiceUnavailable("realtime speech session closed"))
        current = asyncio.current_task()
        if self._reader is not current and not self._reader.done():
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        try:
            await self._connection.close()
        except Exception:
            pass
        close_client = getattr(self._client, "close", None)
        if close_client is not None:
            try:
                await close_client()
            except Exception:
                pass

    async def _read_events(self) -> None:
        try:
            async for event in self._connection:
                event_type = getattr(event, "type", "")
                if event_type == "conversation.item.input_audio_transcription.delta":
                    delta = str(getattr(event, "delta", ""))
                    if not delta:
                        continue
                    self._transcript_parts.append(delta)
                    if self._on_delta is not None:
                        try:
                            await self._on_delta(delta)
                        except Exception:
                            # The browser may have disconnected while the
                            # provider still had a final event in flight.
                            pass
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = str(getattr(event, "transcript", ""))
                    if not transcript:
                        transcript = "".join(self._transcript_parts)
                    if not self._completed.done():
                        self._completed.set_result(transcript)
                    return
                elif event_type == "conversation.item.input_audio_transcription.failed":
                    error = getattr(event, "error", None)
                    message = getattr(error, "message", "provider transcription failed")
                    if not self._completed.done():
                        self._completed.set_exception(VoiceUnavailable(str(message)))
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._completed.done():
                self._completed.set_exception(exc)

    def _record_completion(self) -> None:
        if self._budget_finalized:
            return
        self._budget_finalized = True
        OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        ).record_completion(self._reservation)

    def _record_failure(self, error: BaseException) -> None:
        if self._budget_finalized:
            return
        self._budget_finalized = True
        OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        ).record_failure(self._reservation, error)


class OpenAIRealtimeSTT:
    """Factory for provider-backed incremental transcription sessions."""

    name = "openai_realtime_transcribe"

    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise VoiceUnavailable("OPENAI_API_KEY is not configured")
        self._model = model or settings.openai_realtime_transcription_model
        self._budget = OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        )

    async def start_session(
        self,
        *,
        profile: LanguageProfile,
        on_delta: TranscriptDeltaHandler | None = None,
    ) -> OpenAIRealtimeTranscriptionSession:
        try:
            reservation = self._budget.reserve_fixed(
                model=self._model,
                cost_usd=settings.openai_transcription_reservation_usd,
                operation=f"voice:realtime-transcription:{profile.code}",
            )
        except BudgetError as exc:
            raise VoiceUnavailable(
                "speech-to-text is unavailable because the OpenAI test budget "
                "has been exhausted or its ledger is unsafe"
            ) from exc

        client = None
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            manager = client.realtime.connect(model=self._model)
            connection = await manager.enter()
            with start_span(
                "provider.openai.realtime_transcription",
                {
                    "provider": self.name,
                    "provider.model": self._model,
                    "provider.language": profile.code,
                },
            ):
                await connection.session.update(
                    session={
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {"type": "audio/pcm", "rate": 24000},
                                "transcription": {
                                    "model": self._model,
                                    "language": profile.code,
                                },
                            }
                        },
                    }
                )
        except Exception as exc:
            self._budget.record_failure(reservation, exc)
            if client is not None:
                close_client = getattr(client, "close", None)
                if close_client is not None:
                    try:
                        await close_client()
                    except Exception:
                        pass
            raise VoiceUnavailable("realtime speech-to-text is unavailable") from exc

        log.info(
            "realtime_transcription_started",
            provider=self.name,
            language=profile.code,
        )
        return OpenAIRealtimeTranscriptionSession(
            client=client,
            connection=connection,
            reservation=reservation,
            profile=profile,
            model=self._model,
            on_delta=on_delta,
        )
