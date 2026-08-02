"""Speech to text via OpenAI transcription."""

from __future__ import annotations

from sahaayak_agent.voice.base import STTProvider, VoiceUnavailable
from sahaayak_common import get_logger, settings
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

    async def transcribe(
        self, audio: bytes, *, profile: LanguageProfile, filename: str = "audio.wav"
    ) -> TranscriptionResult:
        # Passing the language explicitly rather than letting the model detect
        # it: the caller already chose one, and autodetection on a short noisy
        # utterance is a common source of a call falling into the wrong
        # language and never recovering.
        response = await self._client.audio.transcriptions.create(
            model=self._model,
            file=(filename, audio),
            language=profile.resolved_stt_locale(),
        )
        text = (response.text or "").strip()
        log.info(
            "transcribed",
            provider=self.name,
            language=profile.code,
            characters=len(text),
            audio_bytes=len(audio),
        )
        return TranscriptionResult(text=text, language_code=profile.code, provider=self.name)
