"""The voice layer the rest of the app talks to.

Synthesis is cache-first because the credit budget is small and the traffic is
extraordinarily repetitive: the same twenty questions are asked of every caller
in every call. Caching them turns a per-call cost into a one-off cost per
phrase per language, which is what makes a live demo affordable.
"""

from __future__ import annotations

import hashlib

from sahaayak_agent.languages import get_profile
from sahaayak_agent.voice.base import STTProvider, TTSProvider, VoiceUnavailable
from sahaayak_agent.voice.openai_stt import OPENAI_EXPLICIT_LANGUAGE_HINTS
from sahaayak_common import (
    get_cache,
    get_effective_provider_policy,
    get_logger,
    provider_rollout_enabled,
    settings,
)
from sahaayak_contracts import LanguageProfile, SynthesisResult, TranscriptionResult

log = get_logger(__name__)

# Canned prompts do not change between deployments, so a long TTL is safe and
# each expiry costs real credits.
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30


def cache_key(text: str, profile: LanguageProfile, model: str) -> str:
    """Content-addressed key covering everything that changes the audio.

    Deliberately not Python's built-in hash(), which is salted per process and
    would silently miss the cache on every restart — the exact case the cache
    exists to prevent.
    """
    digest = hashlib.sha256(
        "\x1f".join(
            [
                text,
                profile.resolved_tts_locale(),
                profile.tts_voice_id,
                profile.tts_provider,
                model,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"tts:{profile.code}:{digest}"


class VoiceService:
    def __init__(
        self, stt: STTProvider | None = None, tts: TTSProvider | None = None
    ) -> None:
        self._stt = stt
        self._sarvam_stt: STTProvider | None = None
        self._tts = tts
        self._realtime_stt = None
        self._stt_ready = stt is not None
        self._tts_ready = tts is not None

    # Providers are constructed lazily so importing this module never requires
    # credentials — the text-only path and the tests must work without them.
    def _get_stt(self) -> STTProvider:
        if self._stt is None:
            from sahaayak_agent.voice.openai_stt import OpenAIWhisperSTT

            self._stt = OpenAIWhisperSTT()
        return self._stt

    def _get_tts(self) -> TTSProvider:
        if self._tts is None:
            from sahaayak_agent.voice.sarvam_tts import SarvamBulbulTTS

            self._tts = SarvamBulbulTTS()
        return self._tts

    def _get_sarvam_stt(self) -> STTProvider:
        if self._sarvam_stt is None:
            from sahaayak_agent.voice.sarvam_stt import SarvamSaarasSTT

            self._sarvam_stt = SarvamSaarasSTT()
        return self._sarvam_stt

    @property
    def stt_available(self) -> bool:
        return self._stt_ready or settings.llm_enabled or settings.tts_enabled

    @property
    def tts_available(self) -> bool:
        return self._tts_ready or settings.tts_enabled

    @property
    def realtime_stt_available(self) -> bool:
        return settings.openai_realtime_stt_enabled and self.stt_available

    async def transcribe(
        self,
        audio: bytes,
        *,
        language_code: str,
        filename: str = "audio.wav",
        subject: str = "",
        state_code: str | None = None,
    ) -> TranscriptionResult:
        if not self.stt_available:
            raise VoiceUnavailable("no speech-to-text provider is configured")
        profile = get_profile(language_code)
        if not provider_rollout_enabled(
            "stt",
            subject=subject,
            language_code=profile.code,
            state_code=state_code,
        ):
            raise VoiceUnavailable("speech-to-text is temporarily paused by operations")
        policy = get_effective_provider_policy("stt", profile.code)
        if not policy["enabled"] or policy["circuit_state"] == "open":
            raise VoiceUnavailable("speech-to-text is temporarily paused by operations")
        provider_name = policy["primary_provider"]
        if (
            provider_name == "openai_whisper"
            and profile.code not in OPENAI_EXPLICIT_LANGUAGE_HINTS
            and policy["fallback_provider"] == "sarvam_saaras"
            and settings.sarvam_api_key
        ):
            provider_name = "sarvam_saaras"
            log.info(
                "stt_fallback_selected_for_language",
                language=profile.code,
                primary_provider=policy["primary_provider"],
                fallback_provider=provider_name,
            )
        if provider_name == "openai_whisper":
            return await self._get_stt().transcribe(audio, profile=profile, filename=filename)
        if provider_name == "sarvam_saaras":
            return await self._get_sarvam_stt().transcribe(
                audio, profile=profile, filename=filename
            )
        raise VoiceUnavailable("the selected speech-to-text provider is not available")

    async def start_realtime_transcription(
        self,
        *,
        language_code: str,
        subject: str = "",
        state_code: str | None = None,
        on_delta=None,
    ):
        """Open an opt-in PCM transcription session for a browser WebSocket."""
        if not self.realtime_stt_available:
            raise VoiceUnavailable("realtime speech-to-text is not enabled")
        profile = get_profile(language_code)
        if not provider_rollout_enabled(
            "stt",
            subject=subject,
            language_code=profile.code,
            state_code=state_code,
        ):
            raise VoiceUnavailable("speech-to-text is temporarily paused by operations")
        policy = get_effective_provider_policy("stt", profile.code)
        if not policy["enabled"] or policy["circuit_state"] == "open":
            raise VoiceUnavailable("speech-to-text is temporarily paused by operations")
        if policy["primary_provider"] not in {"openai_whisper", "openai_realtime_transcribe"}:
            raise VoiceUnavailable("the selected speech-to-text provider is not available")
        if self._realtime_stt is None:
            from sahaayak_agent.voice.openai_realtime_stt import OpenAIRealtimeSTT

            self._realtime_stt = OpenAIRealtimeSTT()
        return await self._realtime_stt.start_session(profile=profile, on_delta=on_delta)

    async def speak(
        self,
        text: str,
        *,
        language_code: str,
        subject: str = "",
        state_code: str | None = None,
    ) -> SynthesisResult:
        if not self.tts_available:
            raise VoiceUnavailable("no text-to-speech provider is configured")

        profile = get_profile(language_code)
        if not provider_rollout_enabled(
            "tts",
            subject=subject,
            language_code=profile.code,
            state_code=state_code,
        ):
            raise VoiceUnavailable("text-to-speech is temporarily paused by operations")
        policy = get_effective_provider_policy("tts", profile.code)
        if not policy["enabled"] or policy["circuit_state"] == "open":
            raise VoiceUnavailable("text-to-speech is temporarily paused by operations")
        if policy["primary_provider"] != "sarvam_bulbul":
            raise VoiceUnavailable("the selected text-to-speech provider is not available")
        provider = self._get_tts()
        key = cache_key(text, profile, getattr(provider, "MODEL", provider.name))

        cache = await get_cache()
        cached = await cache.get(key)
        if cached:
            log.info("tts_cache_hit", language=profile.code, characters=len(text))
            return SynthesisResult(
                audio=cached, provider=provider.name, cached=True, billed_characters=0
            )

        result = await provider.synthesize(text, profile=profile)
        if result.audio:
            await cache.set(key, result.audio, ttl_seconds=CACHE_TTL_SECONDS)
        return result

    async def prewarm(self, phrases: list[str], *, language_code: str) -> int:
        """Synthesise and cache a set of phrases ahead of a demo.

        Run this before recording so the canned questions are already cached
        and the demo neither stutters on first use nor spends credits live.
        """
        warmed = 0
        for phrase in phrases:
            if not phrase.strip():
                continue
            result = await self.speak(phrase, language_code=language_code)
            warmed += 0 if result.cached else 1
        return warmed


_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    global _service
    if _service is None:
        _service = VoiceService()
    return _service
