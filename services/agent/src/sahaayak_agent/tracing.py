"""Langfuse tracing that degrades to a no-op.

Every graph node is wrapped, so a trace shows the reasoning path — what was
understood, which candidates were scored, why a question was chosen — rather
than one opaque call. Tracing stays entirely optional: without Langfuse keys
the decorator returns the function untouched, so nothing about the agent's
behaviour depends on an observability backend being reachable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sahaayak_common import get_logger, settings

log = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _load_observe() -> Callable | None:
    """Find Langfuse's decorator across its v2 and v3 module layouts."""
    try:
        from langfuse import observe  # type: ignore[attr-defined]

        return observe
    except ImportError:
        pass
    try:
        from langfuse.decorators import observe  # type: ignore[no-redef]

        return observe
    except ImportError:
        return None


def traced(name: str) -> Callable[[F], F]:
    """Wrap a graph node so it appears as a named span."""

    def decorator(func: F) -> F:
        if not settings.tracing_enabled:
            return func
        observe = _load_observe()
        if observe is None:
            log.warning("langfuse_not_installed", node=name)
            return func
        try:
            return observe(name=name)(func)
        except Exception as exc:
            log.warning("tracing_decorator_failed", node=name, error=str(exc))
            return func

    return decorator
