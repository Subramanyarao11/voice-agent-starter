"""Speech to text via Sarvam Saaras.

OpenAI Whisper is retained as the primary provider for the launch locales. The
Saaras fallback is selected for Indian locales whose explicit language hint is
not accepted by the OpenAI transcription endpoint, which prevents Telugu,
Bengali, Gujarati, Malayalam, Punjabi, and Odia from being silently detected
as another script.
"""

from __future__ import annotations

import httpx

from sahaayak_agent.tracing import start_span
from sahaayak_agent.voice.base import STTProvider, VoiceUnavailable
from sahaayak_common import (
    ProviderBudgetError,
    ProviderBudgetLedger,
    ProviderBudgetReservation,
    get_logger,
    settings,
)
from sahaayak_contracts import LanguageProfile, TranscriptionResult

log = get_logger(__name__)


class SarvamSaarasSTT(STTProvider):
    name = "sarvam_saaras"

    BASE_URL = "https://api.sarvam.ai/speech-to-text"
    MODEL = "saaras:v3"

    def __init__(self, timeout: float = 30.0) -> None:
        if not settings.sarvam_api_key:
            raise VoiceUnavailable("SARVAM_API_KEY is not configured")
        self._api_key = settings.sarvam_api_key
        self._timeout = timeout
        self._budget = ProviderBudgetLedger(
            "sarvam",
            settings.sarvam_budget_usd,
            settings.resolved_sarvam_budget_ledger_path,
        )

    async def transcribe(
        self, audio: bytes, *, profile: LanguageProfile, filename: str = "audio.wav"
    ) -> TranscriptionResult:
        try:
            reservation: ProviderBudgetReservation = self._budget.reserve_fixed(
                model=self.MODEL,
                cost_usd=settings.sarvam_stt_request_reservation_usd,
                operation=f"voice:transcription:{profile.code}",
            )
        except ProviderBudgetError as exc:
            raise VoiceUnavailable(
                "speech-to-text is unavailable because the Sarvam budget cap "
                "has been reached or its ledger is unsafe"
            ) from exc
        with start_span(
            "provider.sarvam.transcription",
            {
                "provider": self.name,
                "provider.model": self.MODEL,
                "provider.language": profile.code,
                "provider.language_locale": profile.resolved_sarvam_stt_locale(),
                "provider.audio_bytes": len(audio),
            },
        ) as span:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self.BASE_URL,
                        headers={"api-subscription-key": self._api_key},
                        files={"file": (filename, audio, "audio/wav")},
                        data={
                            "model": self.MODEL,
                            "language_code": profile.resolved_sarvam_stt_locale(),
                            "mode": "transcribe",
                        },
                    )
                    response.raise_for_status()
            except Exception as exc:
                self._budget.record_failure(reservation, exc)
                if span is not None:
                    span.record_exception(exc)
                    span.set_attribute("error.type", exc.__class__.__name__)
                raise

        payload = response.json()
        self._budget.record_completion(
            reservation,
            metadata={"language": profile.code, "audio_bytes": len(audio)},
        )
        text = str(payload.get("transcript") or payload.get("text") or "").strip()
        log.info(
            "transcribed",
            provider=self.name,
            language=profile.code,
            characters=len(text),
            audio_bytes=len(audio),
        )
        return TranscriptionResult(text=text, language_code=profile.code, provider=self.name)
