"""Provider interfaces for speech in and speech out.

Kept as two separate interfaces because the choice is genuinely per-direction
and per-language. OpenAI's transcription handles the launch locales, while
Sarvam Saaras provides explicit Indian-language coverage for expansion locales
and Sarvam Bulbul handles vernacular output. A language added later can mix
providers differently without the agent noticing.
"""

from abc import ABC, abstractmethod

from sahaayak_contracts import LanguageProfile, SynthesisResult, TranscriptionResult


class STTProvider(ABC):
    name: str

    @abstractmethod
    async def transcribe(
        self, audio: bytes, *, profile: LanguageProfile, filename: str = "audio.wav"
    ) -> TranscriptionResult: ...


class TTSProvider(ABC):
    name: str

    @abstractmethod
    async def synthesize(self, text: str, *, profile: LanguageProfile) -> SynthesisResult: ...


class VoiceUnavailable(RuntimeError):
    """Raised when a provider is not configured.

    Distinct from a provider failure: a missing key is a deployment state the
    caller-facing layer can degrade around by returning text only, whereas a
    failed call mid-conversation is an error worth surfacing.
    """
