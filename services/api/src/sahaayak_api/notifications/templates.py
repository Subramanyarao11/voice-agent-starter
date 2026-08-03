"""Application-owned message templates and their provider mappings.

Reminder rows store a template key, never a rendered string. That indirection
is what lets a bad Kannada translation or a rejected DLT template be rolled
back by flipping a database row, without touching code or the reminders already
scheduled.

Built-in defaults exist so local development and tests have content without a
seeded database, but they are only a fallback: a database row for the same
key/channel/locale always wins, because that is the row an operator can see and
change. Provider template names stay empty by default — a template that has not
been approved by DLT or Meta must not be presented as ready to send.

The wording is bounded by one rule the eligibility model imposes: a message may
say the caller *may* qualify and point at a source, never that they have been
approved. The deterministic matcher is the only thing that decides eligibility,
and it does not run at reminder time.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from sahaayak_common import NotificationTemplate, get_logger
from sahaayak_contracts import NotificationChannel

log = get_logger(__name__)

# Locale resolution order. English is the terminal fallback because every
# template is authored in it first; a caller never receives an empty message
# because their language's translation has not landed yet.
FALLBACK_LOCALE = "en"

_PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class TemplateNotFound(LookupError):
    """No template exists for this key on this channel in any locale."""


@dataclass(frozen=True, slots=True)
class TemplateContent:
    subject: str = ""
    body: str = ""


@dataclass(frozen=True, slots=True)
class ResolvedTemplate:
    template_key: str
    channel: NotificationChannel
    locale: str
    subject: str
    body: str
    provider_template_name: str = ""
    provider_template_version: str = ""
    dlt_template_id: str = ""
    approval_status: str = "builtin"
    content_revision: int = 0
    # False for any channel whose provider requires a pre-approved template
    # that has not been registered. The dispatcher refuses to send these.
    provider_ready: bool = True


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    template_key: str
    channel: NotificationChannel
    locale: str
    subject: str
    text: str
    html: str = ""
    provider_template_name: str = ""
    # Ordered template variables, for providers that take positional
    # placeholders in an approved template rather than a rendered body.
    variables: tuple[str, ...] = field(default_factory=tuple)


# --- Built-in content -----------------------------------------------------
#
# Short by design. An SMS is billed per segment and Kannada or Hindi text costs
# roughly one segment per 67 characters, so a friendly extra sentence is a real
# recurring cost paid by a service for people who have little money.

_TEXT: dict[str, dict[str, TemplateContent]] = {
    "benefit_reminder": {
        "en": TemplateContent(
            subject="Reminder: {benefit_name}",
            body=(
                "Sahaayak reminder: you may qualify for {benefit_name}. "
                "Check details and apply: {source_url}"
            ),
        ),
        "hi": TemplateContent(
            subject="अनुस्मारक: {benefit_name}",
            body=(
                "सहायक अनुस्मारक: आप {benefit_name} के लिए पात्र हो सकते हैं। "
                "जानकारी देखें: {source_url}"
            ),
        ),
        "kn": TemplateContent(
            subject="ಜ್ಞಾಪನೆ: {benefit_name}",
            body=(
                "ಸಹಾಯಕ ಜ್ಞಾಪನೆ: ನೀವು {benefit_name} ಗೆ ಅರ್ಹರಾಗಿರಬಹುದು. "
                "ವಿವರಗಳನ್ನು ನೋಡಿ: {source_url}"
            ),
        ),
    },
    "application_deadline": {
        "en": TemplateContent(
            subject="Closing soon: {benefit_name}",
            body=(
                "Sahaayak: applications for {benefit_name} close on {due_date}. "
                "Details: {source_url}"
            ),
        ),
        "hi": TemplateContent(
            subject="जल्द बंद: {benefit_name}",
            body=(
                "सहायक: {benefit_name} के आवेदन {due_date} को बंद होंगे। "
                "जानकारी: {source_url}"
            ),
        ),
        "kn": TemplateContent(
            subject="ಶೀಘ್ರದಲ್ಲೇ ಮುಕ್ತಾಯ: {benefit_name}",
            body=(
                "ಸಹಾಯಕ: {benefit_name} ಅರ್ಜಿಗಳು {due_date} ರಂದು ಮುಕ್ತಾಯಗೊಳ್ಳುತ್ತವೆ. "
                "ವಿವರಗಳು: {source_url}"
            ),
        ),
    },
    "benefit_source_link": {
        "en": TemplateContent(
            subject="Source for {benefit_name}",
            body="Sahaayak: official source for {benefit_name}: {source_url}",
        ),
        "hi": TemplateContent(
            subject="{benefit_name} का स्रोत",
            body="सहायक: {benefit_name} का आधिकारिक स्रोत: {source_url}",
        ),
        "kn": TemplateContent(
            subject="{benefit_name} ಮೂಲ",
            body="ಸಹಾಯಕ: {benefit_name} ಅಧಿಕೃತ ಮೂಲ: {source_url}",
        ),
    },
    "contact_verification": {
        "en": TemplateContent(
            subject="Your Sahaayak verification code",
            body="Sahaayak verification code: {code}. Valid for {minutes} minutes.",
        ),
        "hi": TemplateContent(
            subject="आपका सहायक सत्यापन कोड",
            body="सहायक सत्यापन कोड: {code}. {minutes} मिनट के लिए मान्य।",
        ),
        "kn": TemplateContent(
            subject="ನಿಮ್ಮ ಸಹಾಯಕ ಪರಿಶೀಲನಾ ಕೋಡ್",
            body="ಸಹಾಯಕ ಪರಿಶೀಲನಾ ಕೋಡ್: {code}. {minutes} ನಿಮಿಷಗಳವರೆಗೆ ಮಾನ್ಯ.",
        ),
    },
    "human_help_followup": {
        "en": TemplateContent(
            subject="Sahaayak: a volunteer will call you",
            body="Sahaayak: a volunteer will contact you about your question shortly.",
        ),
        "hi": TemplateContent(
            subject="सहायक: एक स्वयंसेवक आपसे संपर्क करेगा",
            body="सहायक: एक स्वयंसेवक जल्द ही आपके प्रश्न के बारे में संपर्क करेगा।",
        ),
        "kn": TemplateContent(
            subject="ಸಹಾಯಕ: ಸ್ವಯಂಸೇವಕರು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ",
            body="ಸಹಾಯಕ: ಸ್ವಯಂಸೇವಕರೊಬ್ಬರು ಶೀಘ್ರದಲ್ಲೇ ನಿಮ್ಮ ಪ್ರಶ್ನೆಯ ಬಗ್ಗೆ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ.",
        ),
    },
    # Operational, sent to an authorized admin contact rather than a caller,
    # so it is English-only and carries no caller data.
    "provider_incident_admin": {
        "en": TemplateContent(
            subject="Sahaayak provider incident: {provider}",
            body="Sahaayak: {provider} {channel} is {state}. Reason: {reason}.",
        ),
    },
}

TEMPLATE_KEYS = tuple(_TEXT)

# Channels whose provider will not accept arbitrary text: the message must
# match a template registered and approved out of band. Sending on these
# without a mapped provider template is a guaranteed rejection, so the
# dispatcher treats a missing mapping as not-ready rather than trying.
PREAPPROVAL_REQUIRED = frozenset({NotificationChannel.SMS, NotificationChannel.WHATSAPP})


def builtin_locales(template_key: str) -> tuple[str, ...]:
    return tuple(_TEXT.get(template_key, {}))


def _builtin(template_key: str, locale: str) -> tuple[TemplateContent, str] | None:
    """Built-in content plus the locale actually used, after fallback."""
    by_locale = _TEXT.get(template_key)
    if not by_locale:
        return None
    for candidate in (locale, FALLBACK_LOCALE):
        content = by_locale.get(candidate)
        if content is not None:
            return content, candidate
    return None


def resolve(
    db: Session | None,
    *,
    template_key: str,
    channel: NotificationChannel,
    locale: str,
) -> ResolvedTemplate:
    """Find the content and provider mapping for one message.

    A database row wins over built-in content, because that row is what an
    operator can inspect, approve, and roll back.
    """
    row = _load_row(db, template_key=template_key, channel=channel, locale=locale)
    if row is not None:
        return ResolvedTemplate(
            template_key=template_key,
            channel=channel,
            locale=row.locale,
            subject=row.subject,
            body=row.body,
            provider_template_name=row.provider_template_name,
            provider_template_version=row.provider_template_version,
            dlt_template_id=row.dlt_template_id,
            approval_status=row.approval_status,
            content_revision=row.content_revision,
            provider_ready=_provider_ready(channel, row.provider_template_name),
        )

    fallback = _builtin(template_key, locale)
    if fallback is None:
        raise TemplateNotFound(f"no template for {template_key} on {channel.value}")

    content, used_locale = fallback
    return ResolvedTemplate(
        template_key=template_key,
        channel=channel,
        locale=used_locale,
        subject=content.subject,
        body=content.body,
        provider_ready=_provider_ready(channel, ""),
    )


def _load_row(
    db: Session | None,
    *,
    template_key: str,
    channel: NotificationChannel,
    locale: str,
) -> NotificationTemplate | None:
    if db is None:
        return None
    rows = db.exec(
        select(NotificationTemplate).where(
            NotificationTemplate.template_key == template_key,
            NotificationTemplate.channel == channel.value,
            NotificationTemplate.active.is_(True),  # type: ignore[union-attr]
            NotificationTemplate.locale.in_([locale, FALLBACK_LOCALE]),  # type: ignore[union-attr]
        )
    ).all()
    if not rows:
        return None
    exact = next((row for row in rows if row.locale == locale), None)
    return exact or next((row for row in rows if row.locale == FALLBACK_LOCALE), None)


def _provider_ready(channel: NotificationChannel, provider_template_name: str) -> bool:
    if channel in PREAPPROVAL_REQUIRED:
        return bool(provider_template_name)
    return True


def render(
    template: ResolvedTemplate, variables: dict[str, str] | None = None
) -> RenderedMessage:
    """Substitute variables into a resolved template.

    Deliberately not ``str.format``: a template is operator-editable content,
    and ``format`` would let a stray brace reach into object attributes. This
    substitutes only known keys and leaves unknown placeholders visible so a
    broken template is obvious rather than silently sending half a sentence.
    """
    values = {key: str(value) for key, value in (variables or {}).items()}

    def substitute(text: str) -> str:
        return _PLACEHOLDER.sub(
            lambda match: values.get(match.group(1), match.group(0)), text
        )

    text = substitute(template.body).strip()
    subject = substitute(template.subject).strip()

    return RenderedMessage(
        template_key=template.template_key,
        channel=template.channel,
        locale=template.locale,
        subject=subject,
        text=text,
        html=_html_body(subject, text),
        provider_template_name=template.provider_template_name,
        # A variable with no supplied value keeps its placeholder here too,
        # matching the rendered text. A provider template parameter that
        # arrives as a literal "{source_url}" is visibly broken, whereas an
        # empty string would send a truncated but plausible-looking message.
        variables=tuple(
            values.get(name, "{" + name + "}") for name in _placeholder_names(template.body)
        ),
    )


def _placeholder_names(body: str) -> tuple[str, ...]:
    """Placeholder names in first-appearance order, without duplicates.

    Order matters: providers that take positional template parameters bind them
    by index, so this must follow the approved template's own ordering.
    """
    seen: list[str] = []
    for match in _PLACEHOLDER.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def _html_body(subject: str, text: str) -> str:
    """A minimal HTML part.

    Every interpolated value is escaped: template variables carry benefit names
    and URLs that originate in scraped source documents, and an unescaped one
    would put attacker-influenced markup into a mailbox.
    """
    safe_subject = html.escape(subject)
    paragraphs = "".join(
        f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip()
    )
    return (
        '<div style="font-family:system-ui,sans-serif;font-size:16px;line-height:1.5">'
        f"<h1 style=\"font-size:18px\">{safe_subject}</h1>{paragraphs}"
        "</div>"
    )
