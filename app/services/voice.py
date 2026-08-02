"""
Voice provider abstraction. STT -> OpenAI Whisper (broad Indic language support,
ample credits). TTS -> Sarvam Bulbul (native-quality Indic voice; OpenAI's TTS
voices are English-centric per our research, not worth the trust risk on
vernacular output). Swappable per-language via Language.stt_provider /
Language.tts_provider so a future language can use a different provider
without touching the agent graph.
"""
from abc import ABC, abstractmethod

import httpx
from openai import OpenAI

from app.core.config import settings


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language_code: str) -> str:
        ...


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        ...


class OpenAIWhisperSTT(STTProvider):
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, language_code: str) -> str:
        # TODO: swap to streaming GPT-Realtime-Whisper for lower latency once
        # the batch flow below is validated end-to-end.
        result = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", audio_bytes),
            language=language_code,
        )
        return result.text


class SarvamBulbulTTS(TTSProvider):
    """
    NOTE: Sarvam credits are limited (~71.55 as of this writing). Cache the
    audio for repeated phrases (the ~15-20 canned dialogue prompts — age,
    income, category questions) in Redis/blob storage via `get_or_synthesize`
    below instead of calling this on every turn.
    """
    BASE_URL = "https://api.sarvam.ai/text-to-speech"

    def __init__(self):
        self.api_key = settings.sarvam_api_key

    async def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"api-subscription-key": self.api_key},
                json={
                    "inputs": [text],
                    "target_language_code": f"{language_code}-IN",
                    "speaker": voice_id or "meera",
                },
                timeout=30,
            )
            resp.raise_for_status()
            # Sarvam returns base64 audio in the response body — decode before
            # returning; left as a TODO since exact field name should be
            # confirmed against current API docs before first real call.
            return resp.content


# --- Registry: language code -> provider instance -----------------------
STT_PROVIDERS: dict[str, STTProvider] = {
    "openai_whisper": OpenAIWhisperSTT(),
}
TTS_PROVIDERS: dict[str, TTSProvider] = {
    "sarvam_bulbul": SarvamBulbulTTS(),
}


async def get_or_synthesize(text: str, language_code: str, voice_id: str, redis_client) -> bytes:
    """Cache-first TTS to conserve Sarvam credits for repeated canned phrases."""
    cache_key = f"tts:{language_code}:{voice_id}:{hash(text)}"
    cached = await redis_client.get(cache_key)
    if cached:
        return cached
    audio = await TTS_PROVIDERS["sarvam_bulbul"].synthesize(text, language_code, voice_id)
    await redis_client.set(cache_key, audio, ex=60 * 60 * 24 * 30)  # 30-day cache
    return audio
