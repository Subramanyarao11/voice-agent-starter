"""Infobip connection configuration, resolved from settings.

Kept separate from the client so tests can construct a configuration directly
against a mock transport without touching process-wide settings, and so the
"is this channel actually usable" question has one answer rather than being
re-derived at each call site.
"""

from __future__ import annotations

from dataclasses import dataclass

from sahaayak_common import settings

# Infobip account hosts look like `xxxxx.api.infobip.com`. Operators paste them
# from the dashboard in every conceivable form, so normalize rather than fail.
_SCHEME_PREFIXES = ("http://", "https://")


def normalize_base_url(raw: str) -> str:
    """Turn a pasted dashboard value into a scheme-qualified origin.

    Accepts ``example.api.infobip.com``, ``https://example.api.infobip.com/``,
    and anything in between. Defaults to HTTPS: an API key must never travel
    over plaintext because someone omitted the scheme.
    """
    value = raw.strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith(_SCHEME_PREFIXES):
        return f"https://{value}"
    return value


def join_url(base_url: str, path: str) -> str:
    return f"{normalize_base_url(base_url)}/{path.lstrip('/')}"


@dataclass(frozen=True, slots=True)
class InfobipConfig:
    base_url: str
    api_key: str
    environment: str = "development"
    timeout_seconds: float = 10.0
    max_retries: int = 2

    sms_sender: str = ""
    email_sender: str = ""
    email_sender_name: str = "Sahaayak"
    whatsapp_sender: str = ""
    voice_number: str = ""

    @classmethod
    def from_settings(cls) -> InfobipConfig:
        return cls(
            base_url=normalize_base_url(settings.infobip_base_url),
            api_key=settings.infobip_api_key.strip(),
            environment=settings.infobip_environment,
            timeout_seconds=max(1.0, settings.infobip_request_timeout_seconds),
            max_retries=max(0, settings.infobip_max_retries),
            sms_sender=settings.infobip_sms_sender.strip(),
            email_sender=settings.infobip_email_sender.strip(),
            email_sender_name=settings.infobip_email_sender_name.strip() or "Sahaayak",
            whatsapp_sender=settings.infobip_whatsapp_sender.strip(),
            voice_number=settings.infobip_voice_number.strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def authorization_header(self) -> str:
        """Infobip's own scheme for API keys, not Bearer and not Basic."""
        return f"App {self.api_key}"

    def url(self, path: str) -> str:
        return join_url(self.base_url, path)
