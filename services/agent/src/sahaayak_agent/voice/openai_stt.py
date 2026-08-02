"""Speech to text via OpenAI transcription."""

from __future__ import annotations

from sahaayak_agent.voice.base import STTProvider, VoiceUnavailable
from sahaayak_common import (
    BudgetError,
    BudgetReservation,
    OpenAIBudgetLedger,
    get_logger,
    settings,
)
from sahaayak_contracts import LanguageProfile, TranscriptionResult

log = get_logger(__name__)


class OpenAIWhisperSTT(STTProvider):
    name = "openai_whisper"

    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise VoiceUnavailable("OPENAI_API_KEY is not configured")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.openai_transcription_model
        self._budget = OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        )

    async def transcribe(
        self, audio: bytes, *, profile: LanguageProfile, filename: str = "audio.wav"
    ) -> TranscriptionResult:
        # Passing the language explicitly rather than letting the model detect
        # it: the caller already chose one, and autodetection on a short noisy
        # utterance is a common source of a call falling into the wrong
        # language and never recovering.
        try:
            reservation: BudgetReservation = self._budget.reserve_fixed(
                model=self._model,
                cost_usd=settings.openai_transcription_reservation_usd,
                operation=f"voice:transcription:{profile.code}",
            )
        except BudgetError as exc:
            raise VoiceUnavailable(
                "speech-to-text is unavailable because the OpenAI test budget "
                "has been exhausted or its ledger is unsafe"
            ) from exc
        try:
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(filename, audio),
                language=profile.resolved_stt_locale(),
            )
        except Exception as exc:
            self._budget.record_failure(reservation, exc)
            raise
        self._budget.record_chat_response(reservation, response)
        text = (response.text or "").strip()
        log.info(
            "transcribed",
            provider=self.name,
            language=profile.code,
            characters=len(text),
            audio_bytes=len(audio),
        )
        return TranscriptionResult(text=text, language_code=profile.code, provider=self.name)
