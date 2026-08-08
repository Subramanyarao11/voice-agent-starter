"""Provider-neutral notification delivery.

Product code imports from here and never from a vendor adapter. The registry
resolves which provider serves a channel using the same audited provider-policy
mechanism the model providers already use, so an operator disables SMS or rolls
back a template through the admin console rather than through a deployment.
"""

from sahaayak_api.notifications.base import NotificationProvider, OutboundNotification
from sahaayak_api.notifications.dispatcher import (
    GATE_FEATURE_ROLLOUT_DISABLED,
    GATE_MESSAGES,
    GATE_OK,
    ChannelAvailability,
    Gate,
    available_channels,
    channel_policy,
    check_channel,
    create_delivery,
    dispatch,
    idempotency_key,
    record_result,
    suppress,
)
from sahaayak_api.notifications.in_app import InAppProvider
from sahaayak_api.notifications.registry import (
    get_provider,
    register_provider,
    reset_providers,
)
from sahaayak_api.notifications.templates import (
    TEMPLATE_KEYS,
    RenderedMessage,
    ResolvedTemplate,
    TemplateNotFound,
    render,
    resolve,
)

__all__ = [
    "GATE_MESSAGES",
    "GATE_FEATURE_ROLLOUT_DISABLED",
    "GATE_OK",
    "TEMPLATE_KEYS",
    "ChannelAvailability",
    "Gate",
    "InAppProvider",
    "NotificationProvider",
    "OutboundNotification",
    "RenderedMessage",
    "ResolvedTemplate",
    "TemplateNotFound",
    "available_channels",
    "channel_policy",
    "check_channel",
    "create_delivery",
    "dispatch",
    "get_provider",
    "idempotency_key",
    "record_result",
    "register_provider",
    "render",
    "reset_providers",
    "resolve",
    "suppress",
]
