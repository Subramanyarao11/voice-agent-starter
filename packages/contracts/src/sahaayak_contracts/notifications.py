"""Provider-neutral notification contracts.

These shapes are what the application reasons about. Nothing here mentions
Infobip, an HTTP status code, or a provider-specific field name, because the
whole point of the adapter boundary is that swapping the provider — or running
with none at all — must not reach the reminder logic, the admin console, or the
browser.

The status vocabulary deliberately distinguishes ``ACCEPTED`` from
``DELIVERED``. A messaging API returning 200 means it took the request, not
that a phone received anything, and collapsing the two would let the product
tell a caller their deadline reminder went out when it silently failed.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


# Channels that leave the system and reach a person through a third party.
# These are the ones requiring a verified contact point and recorded consent.
EXTERNAL_CHANNELS = frozenset(
    {NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.WHATSAPP}
)


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENDING = "sending"
    # The provider took the request. Not evidence that anything was received.
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    SEEN = "seen"
    FAILED = "failed"
    # Deliberately not sent: no consent, provider disabled, budget exhausted.
    # Distinct from FAILED so the admin console can tell a policy decision
    # apart from a provider problem.
    SUPPRESSED = "suppressed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {
        DeliveryStatus.DELIVERED,
        DeliveryStatus.SEEN,
        DeliveryStatus.FAILED,
        DeliveryStatus.SUPPRESSED,
        DeliveryStatus.CANCELLED,
    }
)

# Providers report status out of order routinely: a "delivered" callback can
# arrive before the "accepted" one it supersedes. Ranking lets the webhook
# handler ignore a stale event instead of walking the row backwards.
_STATUS_RANK: dict[DeliveryStatus, int] = {
    DeliveryStatus.QUEUED: 0,
    DeliveryStatus.SENDING: 1,
    DeliveryStatus.ACCEPTED: 2,
    DeliveryStatus.FAILED: 3,
    DeliveryStatus.SUPPRESSED: 3,
    DeliveryStatus.CANCELLED: 3,
    DeliveryStatus.DELIVERED: 4,
    DeliveryStatus.SEEN: 5,
}


def status_rank(status: DeliveryStatus) -> int:
    return _STATUS_RANK[status]


def supersedes(current: DeliveryStatus, incoming: DeliveryStatus) -> bool:
    """Whether ``incoming`` is a later state than ``current``.

    Equal ranks do not supersede, so a duplicate callback is a no-op rather
    than a second write.
    """
    return _STATUS_RANK[incoming] > _STATUS_RANK[current]


class VerificationStatusValue(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    INVALID = "invalid"
    REVOKED = "revoked"


class ConsentStatus(str, Enum):
    UNKNOWN = "unknown"
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"


class ConsentPurpose(str, Enum):
    REMINDERS = "reminders"
    SUPPORT = "support"
    VERIFICATION = "verification"


class ProviderErrorClass(str, Enum):
    """Normalized failure taxonomy shared by every provider adapter.

    The class, not the provider's own code, is what drives retry decisions and
    what the admin console displays — so a provider swap does not rewrite the
    worker's control flow.
    """

    NONE = "none"
    TIMEOUT = "timeout"
    NETWORK = "network"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INVALID_REQUEST = "invalid_request"
    INVALID_DESTINATION = "invalid_destination"
    TEMPLATE_REJECTED = "template_rejected"
    PROVIDER_ERROR = "provider_error"
    MALFORMED_RESPONSE = "malformed_response"
    NOT_CONFIGURED = "not_configured"
    POLICY_DISABLED = "policy_disabled"
    BUDGET_EXHAUSTED = "budget_exhausted"


# Only these classes can plausibly succeed on a second attempt. A rejected
# template or an invalid number will be rejected identically forever, and
# retrying it just spends money and rate-limit budget.
RETRYABLE_ERROR_CLASSES = frozenset(
    {
        ProviderErrorClass.TIMEOUT,
        ProviderErrorClass.NETWORK,
        ProviderErrorClass.RATE_LIMITED,
        ProviderErrorClass.PROVIDER_ERROR,
    }
)


class ProviderSendResult(BaseModel):
    """What every adapter returns, success or failure.

    Adapters do not raise for provider-reported failures. A failed send is a
    recordable delivery outcome, not an exception the caller must catch, and
    modelling it as data is what keeps the worker's state machine readable.
    """

    accepted: bool
    provider: str
    channel: NotificationChannel
    status: DeliveryStatus = DeliveryStatus.QUEUED

    external_message_id: str = ""
    external_bulk_id: str = ""

    provider_status_code: str = ""
    provider_status_group: str = ""
    provider_error_code: str = ""
    error_class: ProviderErrorClass = ProviderErrorClass.NONE
    # Safe for logs and the admin console: never contains a destination, a
    # message body, or a credential.
    error_detail: str = ""

    retryable: bool = False
    retry_after_seconds: int | None = None
    attempt_count: int = 1
    duration_ms: float = 0.0

    cost_minor_units: int | None = None
    cost_currency: str = ""

    @classmethod
    def failure(
        cls,
        *,
        provider: str,
        channel: NotificationChannel,
        error_class: ProviderErrorClass,
        detail: str = "",
        status: DeliveryStatus = DeliveryStatus.FAILED,
        **extra: object,
    ) -> "ProviderSendResult":
        return cls(
            accepted=False,
            provider=provider,
            channel=channel,
            status=status,
            error_class=error_class,
            error_detail=detail,
            retryable=error_class in RETRYABLE_ERROR_CLASSES,
            **extra,  # type: ignore[arg-type]
        )


class DeliveryStatusUpdate(BaseModel):
    """A normalized provider callback, before it touches the database."""

    external_message_id: str
    channel: NotificationChannel
    status: DeliveryStatus
    provider: str = ""
    provider_status_code: str = ""
    provider_status_group: str = ""
    provider_error_code: str = ""
    error_class: ProviderErrorClass = ProviderErrorClass.NONE
    occurred_at: datetime | None = None
    cost_minor_units: int | None = None
    cost_currency: str = ""
    # Set when the provider reports the destination itself is unusable, so the
    # contact point can be marked invalid rather than retried forever.
    destination_invalid: bool = False
    # Set by STOP replies, complaints, and unsubscribes.
    consent_revoked: bool = False
    callback_reference: str = ""


class InboundMessage(BaseModel):
    """An inbound message from any channel, normalized for the agent.

    ``external_user_key`` is a hashed channel identity. It is never a phone
    number, and it never authorizes anything on its own — a WhatsApp sender
    string is something a third party asserts, not proof of who is asking.
    """

    channel: NotificationChannel
    external_user_key: str
    locale: str = ""
    text: str = ""
    media_reference: str = ""
    media_mime_type: str = ""
    user_initiated: bool = True
    consent_context: ConsentStatus = ConsentStatus.UNKNOWN
    received_at: datetime | None = None
    provider_message_id: str = ""
    safe_metadata: dict[str, str] = Field(default_factory=dict)
