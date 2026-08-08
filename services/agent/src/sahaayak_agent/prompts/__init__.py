"""Per-language phrase catalogs and the lookup that resolves them.

Adding a language is adding a module here with the same keys as `en`. Missing
keys fall back to English and log a warning rather than raising, so a partly
translated language degrades to bilingual output instead of a failed call.
The release validator and Admin → Languages gate remain responsible for
preventing an incomplete or machine-assisted bundle from being activated.
"""

from importlib import import_module

from sahaayak_agent.languages import ALL_PROFILES
from sahaayak_agent.prompts import en, hi, kn
from sahaayak_common import get_logger

log = get_logger(__name__)

CATALOGS: dict[str, dict[str, str]] = {
    "en": en.PHRASES,
    "hi": hi.PHRASES,
    "kn": kn.PHRASES,
}
BUNDLE_REVIEW_STATUS: dict[str, str] = {
    "en": getattr(en, "REVIEW_STATUS", "unspecified"),
    "hi": getattr(hi, "REVIEW_STATUS", "unspecified"),
    "kn": getattr(kn, "REVIEW_STATUS", "unspecified"),
}

# Expansion bundles are deliberately discovered by locale code. A reviewed
# bundle can therefore be added as `prompts/<code>.py` without changing the
# dialogue graph or risking a code-path fork. Missing modules remain absent
# from `supported_languages()` and the admin release gate cannot approve them.
for _profile in ALL_PROFILES:
    if _profile.code in CATALOGS:
        continue
    try:
        _module = import_module(f"{__name__}.{_profile.code}")
    except ModuleNotFoundError:
        continue
    _phrases = getattr(_module, "PHRASES", None)
    if isinstance(_phrases, dict) and all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in _phrases.items()
    ):
        CATALOGS[_profile.code] = _phrases
        BUNDLE_REVIEW_STATUS[_profile.code] = getattr(
            _module, "REVIEW_STATUS", "unspecified"
        )

FALLBACK_LANGUAGE = "en"


class PromptCatalog:
    """Phrase lookup for one language."""

    def __init__(self, language_code: str) -> None:
        self.language_code = language_code
        self._phrases = CATALOGS.get(language_code, {})
        self._fallback = CATALOGS[FALLBACK_LANGUAGE]
        if language_code not in CATALOGS:
            log.warning(
                "no_prompt_catalog_for_language",
                language_code=language_code,
                using=FALLBACK_LANGUAGE,
            )

    def has(self, key: str) -> bool:
        return key in self._phrases

    def render(self, key: str, **params: object) -> str:
        template = self._phrases.get(key)
        if template is None:
            template = self._fallback.get(key)
            if template is None:
                log.error("missing_prompt_key", key=key, language_code=self.language_code)
                return ""
            log.warning(
                "prompt_key_untranslated",
                key=key,
                language_code=self.language_code,
            )
        try:
            return template.format(**params)
        except KeyError as exc:
            log.error(
                "prompt_missing_parameter",
                key=key,
                language_code=self.language_code,
                parameter=str(exc),
            )
            return template


_catalogs: dict[str, PromptCatalog] = {}


def get_catalog(language_code: str) -> PromptCatalog:
    if language_code not in _catalogs:
        _catalogs[language_code] = PromptCatalog(language_code)
    return _catalogs[language_code]


def supported_languages() -> list[str]:
    return sorted(CATALOGS)


def bundle_review_status(language_code: str) -> str:
    """Return the provenance label for the installed prompt bundle."""
    return BUNDLE_REVIEW_STATUS.get(language_code, "missing")


def missing_keys(language_code: str) -> list[str]:
    """Keys a language still needs. Used by the translation-coverage test."""
    return sorted(set(CATALOGS[FALLBACK_LANGUAGE]) - set(CATALOGS.get(language_code, {})))


__all__ = [
    "CATALOGS",
    "BUNDLE_REVIEW_STATUS",
    "PromptCatalog",
    "bundle_review_status",
    "get_catalog",
    "missing_keys",
    "supported_languages",
]
