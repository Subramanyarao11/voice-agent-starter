"""Language and speech contracts.

A language is a configuration record, not a code path. Each profile carries the
locale strings its providers expect, because Whisper and Sarvam disagree on how
to name the same language — Whisper wants `kn`, Sarvam wants `kn-IN`. Keeping
both here stops that mismatch from leaking into the agent.
"""

from pydantic import BaseModel, Field


class LanguageProfile(BaseModel):
    code: str  # ISO 639-1: "kn", "hi", "ta", "te", "mr"
    name: str  # English name, for logs and the admin view
    native_name: str  # shown in the demo UI's language picker

    stt_provider: str = "openai_whisper"
    stt_locale: str = ""  # defaults to `code`

    tts_provider: str = "sarvam_bulbul"
    tts_locale: str = ""  # defaults to f"{code}-IN"
    tts_voice_id: str = "anushka"

    def resolved_stt_locale(self) -> str:
        return self.stt_locale or self.code

    def resolved_tts_locale(self) -> str:
        return self.tts_locale or f"{self.code}-IN"


class TranscriptionResult(BaseModel):
    text: str
    language_code: str
    provider: str
    # Whisper does not always return a confidence, so this stays optional
    # rather than being faked with a default.
    confidence: float | None = None


class SynthesisResult(BaseModel):
    audio: bytes
    mime_type: str = "audio/wav"
    provider: str
    cached: bool = False
    # Character count actually billed. Cache hits report zero, which is what
    # makes the remaining-credit estimate meaningful.
    billed_characters: int = 0


class LanguageCatalog(BaseModel):
    """The set of languages the deployment currently serves."""

    profiles: list[LanguageProfile] = Field(default_factory=list)

    def get(self, code: str) -> LanguageProfile | None:
        return next((p for p in self.profiles if p.code == code), None)
