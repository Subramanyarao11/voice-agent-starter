"""Text to speech via Sarvam's Bulbul.

Sarvam accepts a limited number of characters per request, and a full
eligibility answer routinely exceeds it. Rather than truncating — which would
cut a caller off mid-sentence, in the middle of the part that matters — long
text is split on sentence boundaries and the returned WAV chunks are stitched
back into one stream.
"""

from __future__ import annotations

import base64
import io
import re
import wave

import httpx

from sahaayak_agent.voice.base import TTSProvider, VoiceUnavailable
from sahaayak_common import get_logger, settings
from sahaayak_contracts import LanguageProfile, SynthesisResult

log = get_logger(__name__)

# Sarvam's documented per-request ceiling is 500 characters; staying under it
# leaves room for the sentence splitter to avoid awkward breaks.
MAX_CHUNK_CHARACTERS = 450

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।])\s+")


def split_for_synthesis(text: str, limit: int = MAX_CHUNK_CHARACTERS) -> list[str]:
    """Split on sentence boundaries, packing as much as fits into each chunk.

    The Devanagari danda (।) is a sentence terminator too, so it is treated as
    one — without it, Hindi text would never split and would always be one
    oversized chunk.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_BOUNDARY.split(text):
        if not sentence:
            continue
        if len(sentence) > limit:
            # A single sentence longer than the limit has no good break point,
            # so fall back to hard slicing rather than dropping it.
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                sentence[i : i + limit] for i in range(0, len(sentence), limit)
            )
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def merge_wav(chunks: list[bytes]) -> bytes:
    """Concatenate WAV payloads into one, keeping a single valid header.

    Naively joining the bytes would embed a RIFF header partway through the
    audio and most players would stop at the first one.
    """
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]

    output = io.BytesIO()
    writer: wave.Wave_write | None = None
    try:
        for chunk in chunks:
            with wave.open(io.BytesIO(chunk), "rb") as reader:
                if writer is None:
                    writer = wave.open(output, "wb")
                    writer.setnchannels(reader.getnchannels())
                    writer.setsampwidth(reader.getsampwidth())
                    writer.setframerate(reader.getframerate())
                writer.writeframes(reader.readframes(reader.getnframes()))
    except wave.Error as exc:
        log.warning("wav_merge_failed_returning_first_chunk", error=str(exc))
        return chunks[0]
    finally:
        if writer is not None:
            writer.close()
    return output.getvalue()


class SarvamBulbulTTS(TTSProvider):
    name = "sarvam_bulbul"

    BASE_URL = "https://api.sarvam.ai/text-to-speech"
    MODEL = "bulbul:v2"

    def __init__(self, timeout: float = 30.0) -> None:
        if not settings.sarvam_api_key:
            raise VoiceUnavailable("SARVAM_API_KEY is not configured")
        self._api_key = settings.sarvam_api_key
        self._timeout = timeout

    async def synthesize(self, text: str, *, profile: LanguageProfile) -> SynthesisResult:
        chunks = split_for_synthesis(text)
        if not chunks:
            return SynthesisResult(audio=b"", provider=self.name, billed_characters=0)

        audio_parts: list[bytes] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for chunk in chunks:
                response = await client.post(
                    self.BASE_URL,
                    headers={"api-subscription-key": self._api_key},
                    json={
                        "text": chunk,
                        "target_language_code": profile.resolved_tts_locale(),
                        "speaker": profile.tts_voice_id,
                        "model": self.MODEL,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                encoded = (payload.get("audios") or [None])[0]
                if not encoded:
                    log.error("sarvam_returned_no_audio", keys=sorted(payload))
                    continue
                audio_parts.append(base64.b64decode(encoded))

        billed = sum(len(chunk) for chunk in chunks)
        log.info(
            "synthesized",
            provider=self.name,
            language=profile.code,
            chunks=len(chunks),
            billed_characters=billed,
        )
        return SynthesisResult(
            audio=merge_wav(audio_parts),
            provider=self.name,
            billed_characters=billed,
        )
