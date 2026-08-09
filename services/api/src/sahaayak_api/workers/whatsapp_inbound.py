"""Handling an inbound WhatsApp message.

Runs after the webhook has already answered, because a turn through the agent
graph — and a transcription before it, for a voice note — takes far longer than
a provider will wait before deciding the callback failed and retrying it.

The identity rules here are the whole point of the module. A WhatsApp sender is
a string Meta hands to Infobip which hands it to us. It is hashed on arrival,
it is used only as a stable conversation key, and it is never merged with a
browser session — someone who knows a phone number must not be able to reach
another person's saved benefits by messaging from it.

What the agent does with the turn is unchanged from the browser: the same
graph, the same deterministic matcher, the same escalation. Only the transport
differs.
"""

from __future__ import annotations

from sahaayak_agent import to_response
from sahaayak_api.deps import get_runtime, get_voice
from sahaayak_api.integrations.infobip.whatsapp import (
    InfobipWhatsAppProvider,
    build_whatsapp_provider,
    open_window,
)
from sahaayak_api.notifications import get_provider
from sahaayak_api.rate_limit import RateLimitUnavailable, consume_channel_limit
from sahaayak_common import (
    UserSession,
    channel_identity_hash,
    get_logger,
    new_id,
    session_scope,
    settings,
)
from sahaayak_contracts import NotificationChannel

log = get_logger(__name__)

# Per-sender budgets are independent of browser limits so a WhatsApp flood
# cannot exhaust the protection on the web demo or spend the shared provider
# cap through a second transport.
INBOUND_WINDOW_SECONDS = 60

# Answers that need no agent turn, so they cost nothing and cannot be made to
# spend a model call. English only for now: a caller who has not yet completed
# a turn has no known language, and these are dead ends rather than dialogue.
UNSUPPORTED_MEDIA_REPLY = (
    "Sorry, I can only read text and voice messages. "
    "Please type your question or send a voice note."
)
LOCATION_REPLY = (
    "Thanks. I have not saved your location. "
    "Please tell me your district in a message if it matters for a scheme."
)
BUSY_REPLY = "You are sending messages very quickly. Please wait a moment and try again."


async def handle_event(event: dict) -> None:
    """Process one normalized inbound WhatsApp event.

    Never raises. This runs detached from the request that scheduled it, so an
    exception here would surface only as an unhandled task and the caller would
    simply never get a reply.
    """
    try:
        await _handle(event)
    except Exception as exc:
        log.error(
            "whatsapp_inbound_failed",
            error=str(exc),
            error_type=exc.__class__.__name__,
            kind=event.get("kind"),
            exc_info=True,
        )


async def _handle(event: dict) -> None:
    sender = event.get("sender") or ""
    if not sender:
        return

    identity = channel_identity_hash("whatsapp", sender)
    provider = build_whatsapp_provider() or _registered_provider()
    if provider is None:
        log.info("whatsapp_inbound_ignored", reason="no_provider", identity=identity[:12])
        return

    # The window opens on any inbound message, including ones we decline to
    # act on: the user did message us, and that is what Meta's rule turns on.
    await open_window(sender)

    try:
        decision = await consume_channel_limit(
            identity,
            bucket="whatsapp_inbound",
            limit=settings.rate_limit_whatsapp_inbound_per_sender,
            window_seconds=INBOUND_WINDOW_SECONDS,
        )
        daily_decision = await consume_channel_limit(
            identity,
            bucket="whatsapp_inbound_daily",
            limit=settings.rate_limit_whatsapp_inbound_per_sender_per_day,
            window_seconds=86_400,
        )
    except RateLimitUnavailable:
        # Do not turn a limiter outage into an unbounded paid channel. The
        # webhook has already been acknowledged; the provider will not get an
        # AI response until Redis protection is healthy again.
        log.error("whatsapp_rate_limiter_unavailable", identity=identity[:12])
        return
    if not decision.allowed:
        await _reply(provider, sender, BUSY_REPLY, identity=identity)
        return
    if not daily_decision.allowed:
        await _reply(provider, sender, BUSY_REPLY, identity=identity)
        return

    kind = event.get("kind")
    if kind == "UNSUPPORTED":
        await _reply(provider, sender, UNSUPPORTED_MEDIA_REPLY, identity=identity)
        return
    if kind == "LOCATION":
        await _reply(provider, sender, LOCATION_REPLY, identity=identity)
        return

    transcript = await _transcript_for(event, provider=provider, identity=identity)
    if not transcript:
        await _reply(provider, sender, UNSUPPORTED_MEDIA_REPLY, identity=identity)
        return

    caller_id = _ensure_channel_session(identity)
    runtime = get_runtime()
    session, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript=transcript,
        language_code=None,
        state_code=None,
    )
    response = to_response(session, state)

    log.info(
        "whatsapp_turn_completed",
        identity=identity[:12],
        intent=state.intent.value,
        matches=len(response.matches),
        escalated=state.needs_escalation,
    )
    await _reply(provider, sender, response.response_text, identity=identity)


async def _transcript_for(
    event: dict, *, provider: InfobipWhatsAppProvider, identity: str
) -> str:
    kind = event.get("kind")
    if kind in ("TEXT", "ACTION"):
        return str(event.get("text") or "").strip()[:2000]

    if kind != "AUDIO":
        return ""

    media = await provider.download_media(str(event.get("media_id") or ""))
    if not media:
        return ""

    voice = get_voice()
    if not voice.stt_available:
        return ""

    try:
        # Called in-process rather than through a loopback request to the
        # public voice route: that route authenticates a browser session, which
        # a WhatsApp user does not have and must not be given.
        transcription = await voice.transcribe(media, language_code=None, filename="voice.ogg")
    except Exception as exc:
        log.warning(
            "whatsapp_transcription_failed",
            identity=identity[:12],
            error=exc.__class__.__name__,
        )
        return ""
    finally:
        # The bytes are dropped here regardless. A voice note is someone
        # describing their income and family out loud.
        del media

    return transcription.text.strip()[:2000]


def _ensure_channel_session(identity: str) -> str:
    """Get or create the conversation session for a hashed WhatsApp identity.

    Marked ``auth_mode="whatsapp"`` so it can never satisfy the browser session
    dependency, which requires ``guest``. A WhatsApp identity therefore cannot
    be used to read saved benefits or contact points through the web API.
    """
    with session_scope() as db:
        existing = db.query(UserSession).filter_by(phone_or_session_id=identity).first()
        if existing is not None:
            return identity
        db.add(
            UserSession(
                id=new_id("ses"),
                phone_or_session_id=identity,
                auth_mode="whatsapp",
                state_code=settings.default_state,
                language_code=settings.default_language,
            )
        )
    return identity


async def _reply(
    provider: InfobipWhatsAppProvider, sender: str, text: str, *, identity: str
) -> None:
    if not text.strip():
        return
    result = await provider.send_reply(
        destination=sender, text=text, internal_message_id=new_id("msg")
    )
    if not result.accepted:
        log.warning(
            "whatsapp_reply_not_delivered",
            identity=identity[:12],
            error_class=result.error_class.value,
        )


def _registered_provider() -> InfobipWhatsAppProvider | None:
    """Any provider a test or deployment bound explicitly for this channel."""
    candidate = get_provider(NotificationChannel.WHATSAPP, allow_fallback=False)
    return candidate if isinstance(candidate, InfobipWhatsAppProvider) else candidate  # type: ignore[return-value]
