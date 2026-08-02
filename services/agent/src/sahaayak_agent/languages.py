"""The language catalog the deployment ships with.

Kannada and Hindi are the languages targeted for the submission demo. The other
three are listed because the pipeline and prompts are the only work each one
needs — they are here to make the remaining effort concrete rather than to
claim coverage that does not exist yet.
"""

from sahaayak_contracts import LanguageCatalog, LanguageProfile

# Sarvam's Bulbul v2 speakers. Voice choice is per language rather than global
# because a voice that sounds natural in Hindi can sound off in Kannada.
DEFAULT_CATALOG = LanguageCatalog(
    profiles=[
        LanguageProfile(
            code="kn",
            name="Kannada",
            native_name="ಕನ್ನಡ",
            tts_voice_id="anushka",
        ),
        LanguageProfile(
            code="hi",
            name="Hindi",
            native_name="हिन्दी",
            tts_voice_id="anushka",
        ),
        LanguageProfile(
            code="en",
            name="English",
            native_name="English",
            tts_locale="en-IN",
            tts_voice_id="anushka",
        ),
    ]
)

# Ready for data and prompts; not served until both exist.
PLANNED_PROFILES = [
    LanguageProfile(code="ta", name="Tamil", native_name="தமிழ்", tts_voice_id="anushka"),
    LanguageProfile(code="te", name="Telugu", native_name="తెలుగు", tts_voice_id="anushka"),
    LanguageProfile(code="mr", name="Marathi", native_name="मराठी", tts_voice_id="anushka"),
]


DEFAULT_STATES: list[tuple[str, str, str]] = [
    # (state code, name, primary language)
    ("KA", "Karnataka", "kn"),
    ("MH", "Maharashtra", "mr"),
    ("TN", "Tamil Nadu", "ta"),
    ("TS", "Telangana", "te"),
    ("DL", "Delhi", "hi"),
]


def get_profile(code: str) -> LanguageProfile:
    """Resolve a language, falling back to English rather than failing a call."""
    return DEFAULT_CATALOG.get(code) or DEFAULT_CATALOG.get("en")  # type: ignore[return-value]
