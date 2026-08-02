"""Per-language phrase catalogs and the lookup that resolves them.

Adding a language is adding a module here with the same keys as `en`. Missing
keys fall back to English and log a warning rather than raising, so a partly
translated language degrades to bilingual output instead of a failed call —
during a build week, half-translated beats broken.
"""

from sahaayak_agent.prompts import en, hi, kn
from sahaayak_common import get_logger

log = get_logger(__name__)

CATALOGS: dict[str, dict[str, str]] = {
    "en": en.PHRASES,
    "hi": hi.PHRASES,
    "kn": kn.PHRASES,
}

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


def missing_keys(language_code: str) -> list[str]:
    """Keys a language still needs. Used by the translation-coverage test."""
    return sorted(set(CATALOGS[FALLBACK_LANGUAGE]) - set(CATALOGS.get(language_code, {})))


__all__ = [
    "CATALOGS",
    "PromptCatalog",
    "get_catalog",
    "missing_keys",
    "supported_languages",
]
