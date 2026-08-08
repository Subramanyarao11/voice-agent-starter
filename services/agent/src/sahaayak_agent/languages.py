"""The language rollout catalog.

English, Kannada, and Hindi are the launch profiles. Eight additional Indian
language profiles are registered as inactive rollout targets, making eleven
profiles in the complete catalog. Registration is deliberately separate from
activation: prompts, localized content, provider evidence, and native review
must be recorded before an expansion locale is served.
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

# Ready for data and prompts; not served until evidence and review gates pass.
# Together with the three launch profiles this is the eleven-profile catalog.
PLANNED_PROFILES = [
    LanguageProfile(code="ta", name="Tamil", native_name="தமிழ்", tts_voice_id="anushka"),
    LanguageProfile(code="te", name="Telugu", native_name="తెలుగు", tts_voice_id="anushka"),
    LanguageProfile(code="mr", name="Marathi", native_name="मराठी", tts_voice_id="anushka"),
    LanguageProfile(code="bn", name="Bengali", native_name="বাংলা", tts_voice_id="anushka"),
    LanguageProfile(code="gu", name="Gujarati", native_name="ગુજરાતી", tts_voice_id="anushka"),
    LanguageProfile(code="ml", name="Malayalam", native_name="മലയാളം", tts_voice_id="anushka"),
    LanguageProfile(code="pa", name="Punjabi", native_name="ਪੰਜਾਬੀ", tts_voice_id="anushka"),
    LanguageProfile(
        code="or",
        name="Odia",
        native_name="ଓଡ଼ିଆ",
        sarvam_stt_locale="od-IN",
        tts_locale="od-IN",
        tts_voice_id="anushka",
    ),
]

ALL_PROFILES = [*DEFAULT_CATALOG.profiles, *PLANNED_PROFILES]


DEFAULT_STATES: list[tuple[str, str, str]] = [
    # (state code, name, primary language)
    ("AN", "Andaman and Nicobar Islands", "en"),
    ("AP", "Andhra Pradesh", "te"),
    ("AR", "Arunachal Pradesh", "en"),
    ("AS", "Assam", "bn"),
    ("BR", "Bihar", "hi"),
    ("CH", "Chandigarh", "hi"),
    ("CG", "Chhattisgarh", "hi"),
    ("ND", "Dadra and Nagar Haveli and Daman and Diu", "hi"),
    ("DL", "Delhi", "hi"),
    ("GA", "Goa", "en"),
    ("GJ", "Gujarat", "gu"),
    ("HR", "Haryana", "hi"),
    ("HP", "Himachal Pradesh", "hi"),
    ("JK", "Jammu and Kashmir", "hi"),
    ("JH", "Jharkhand", "hi"),
    ("KA", "Karnataka", "kn"),
    ("KL", "Kerala", "ml"),
    ("LA", "Ladakh", "hi"),
    ("LD", "Lakshadweep", "ml"),
    ("MP", "Madhya Pradesh", "hi"),
    ("MH", "Maharashtra", "mr"),
    ("MN", "Manipur", "en"),
    ("ML", "Meghalaya", "en"),
    ("MZ", "Mizoram", "en"),
    ("NL", "Nagaland", "en"),
    ("OD", "Odisha", "or"),
    ("PY", "Puducherry", "ta"),
    ("PB", "Punjab", "pa"),
    ("RJ", "Rajasthan", "hi"),
    ("SK", "Sikkim", "en"),
    ("TN", "Tamil Nadu", "ta"),
    ("TS", "Telangana", "te"),
    ("TR", "Tripura", "bn"),
    ("UP", "Uttar Pradesh", "hi"),
    ("UK", "Uttarakhand", "hi"),
    ("WB", "West Bengal", "bn"),
]


def get_profile(code: str) -> LanguageProfile:
    """Resolve a language, falling back to English rather than failing a call."""
    normalized = code.strip().lower()
    return next(
        (profile for profile in ALL_PROFILES if profile.code == normalized),
        DEFAULT_CATALOG.get("en"),
    )  # type: ignore[return-value]
