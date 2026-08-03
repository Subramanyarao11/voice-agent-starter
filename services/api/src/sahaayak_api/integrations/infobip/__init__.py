"""Infobip provider adapter.

Import from here rather than from the submodules, so the surface the rest of
the API depends on stays small and the internals can be reorganized without a
repo-wide edit.
"""

from sahaayak_api.integrations.infobip.client import (
    InfobipClient,
    InfobipResponse,
    get_infobip_client,
    reset_infobip_client,
    shutdown_infobip_client,
)
from sahaayak_api.integrations.infobip.config import InfobipConfig, join_url, normalize_base_url
from sahaayak_api.integrations.infobip.errors import (
    InfobipError,
    classify_status,
    parse_retry_after,
    refine_error_class,
)

__all__ = [
    "InfobipClient",
    "InfobipConfig",
    "InfobipError",
    "InfobipResponse",
    "classify_status",
    "get_infobip_client",
    "join_url",
    "normalize_base_url",
    "parse_retry_after",
    "refine_error_class",
    "reset_infobip_client",
    "shutdown_infobip_client",
]
