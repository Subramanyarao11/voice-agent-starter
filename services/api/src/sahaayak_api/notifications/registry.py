"""Choosing which provider serves a channel.

The mapping is late-bound rather than wired at import: the adapters need
settings and an HTTP client that may not exist yet at import time, and tests
need to substitute a fake without patching module internals.

Falling back to in-app is a real product decision, not a convenience. A caller
who asked for an SMS reminder and got an in-app one still has the reminder;
a caller who got an exception has nothing.
"""

from __future__ import annotations

from collections.abc import Callable

from sahaayak_api.notifications.base import NotificationProvider
from sahaayak_api.notifications.in_app import InAppProvider
from sahaayak_common import get_logger
from sahaayak_contracts import NotificationChannel

log = get_logger(__name__)

ProviderFactory = Callable[[], NotificationProvider | None]

_overrides: dict[NotificationChannel, NotificationProvider] = {}


def register_provider(
    channel: NotificationChannel, provider: NotificationProvider | None
) -> None:
    """Bind a provider to a channel, or clear the binding when None.

    Used by tests and by any deployment that swaps a channel's vendor without
    changing product code.
    """
    if provider is None:
        _overrides.pop(channel, None)
        return
    _overrides[channel] = provider


def reset_providers() -> None:
    _overrides.clear()


def _default_provider(channel: NotificationChannel) -> NotificationProvider | None:
    if channel is NotificationChannel.IN_APP:
        return InAppProvider()

    # Imported lazily: building an adapter reads settings and may construct an
    # HTTP client, and importing this module must require neither. Each builder
    # returns None when its channel is not configured, so an unconfigured
    # deployment falls through to the in-app fallback below.
    if channel is NotificationChannel.EMAIL:
        from sahaayak_api.integrations.infobip.email import build_email_provider

        return build_email_provider()
    if channel is NotificationChannel.SMS:
        from sahaayak_api.integrations.infobip.sms import build_sms_provider

        return build_sms_provider()
    if channel is NotificationChannel.WHATSAPP:
        from sahaayak_api.integrations.infobip.whatsapp import build_whatsapp_provider

        return build_whatsapp_provider()
    return None


def get_provider(
    channel: NotificationChannel, *, allow_fallback: bool = True
) -> NotificationProvider | None:
    """The provider serving ``channel``, or the in-app fallback.

    Returns None only when the channel has no provider and fallback is
    refused — the caller then decides whether that is an error or a skip.
    """
    override = _overrides.get(channel)
    if override is not None:
        return override

    provider = _default_provider(channel)
    if provider is not None and provider.available():
        return provider

    if not allow_fallback or channel is NotificationChannel.IN_APP:
        return None

    log.info(
        "notification_provider_falling_back",
        channel=channel.value,
        fallback="in_app",
        reason="provider_unavailable",
    )
    return InAppProvider()
