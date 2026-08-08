"""Speech to text via OpenAI transcription."""

from __future__ import annotations

from sahaayak_agent.tracing import start_span
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

# The transcription endpoint rejects an explicit language hint for several
# Indian locales even though the model can still detect their speech. Keep
# explicit hints for the locales accepted by the endpoint and let it detect
# the remaining supported catalog languages instead of failing the request.
OPENAI_EXPLICIT_LANGUAGE_HINTS = frozenset({"en", "hi", "kn", "ta", "mr"})


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
        # Prefer an explicit hint when the endpoint accepts it. For catalog
        # locales that the endpoint rejects as a parameter, omit the hint and
        # let the model detect the already-selected Indian language.
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
        with start_span(
            "provider.openai.transcription",
            {
                "provider": self.name,
                "provider.model": self._model,
                "provider.language": profile.code,
                "provider.audio_bytes": len(audio),
            },
        ) as span:
            try:
                request = {
                    "model": self._model,
                    "file": (filename, audio),
                }
                if profile.resolved_stt_locale() in OPENAI_EXPLICIT_LANGUAGE_HINTS:
                    request["language"] = profile.resolved_stt_locale()
                else:
                    log.info(
                        "transcription_language_autodetect",
                        language=profile.code,
                        provider=self.name,
                    )
                response = await self._client.audio.transcriptions.create(**request)
            except Exception as exc:
                self._budget.record_failure(reservation, exc)
                if span is not None:
                    span.record_exception(exc)
                    span.set_attribute("error.type", exc.__class__.__name__)
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
