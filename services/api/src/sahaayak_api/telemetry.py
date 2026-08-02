"""Redacted telemetry and audit helpers shared by API routes and middleware."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sahaayak_agent.tracing import current_langfuse_trace, current_otel_trace_id
from sahaayak_api.admin_auth import AdminPrincipal
from sahaayak_common import (
    AuditEvent,
    TelemetryEvent,
    get_logger,
    new_id,
    request_id_var,
    session_scope,
)

log = get_logger(__name__)


def _safe_metadata(value: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    """Keep dimensions primitive and bounded; never persist arbitrary payloads."""
    if not value:
        return {}
    safe: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if len(safe) >= 12:
            break
        if not isinstance(key, str) or len(key) > 64:
            continue
        if isinstance(item, (str, int, float, bool)):
            safe[key] = str(item)[:160] if isinstance(item, str) else item
    return safe


def record_telemetry(
    *,
    event_type: str,
    route: str = "",
    method: str = "",
    status_code: int | None = None,
    trace_id: str | None = None,
    trace_url: str | None = None,
    duration_ms: float | None = None,
    surface: str = "system",
    language_code: str | None = None,
    state_code: str | None = None,
    provider: str | None = None,
    outcome: str = "",
    error_code: str | None = None,
    safe_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Persist one safe event without making the user request fail.

    Telemetry is valuable, but it must never become a new availability or
    privacy failure mode. The request ID is taken from the current context and
    no body, transcript, audio, or profile data is accepted here.
    """
    try:
        langfuse_trace_id, langfuse_trace_url = current_langfuse_trace()
        with session_scope() as db:
            db.add(
                TelemetryEvent(
                    id=new_id("tel"),
                    event_type=event_type,
                    request_id=request_id_var.get(),
                    trace_id=trace_id or current_otel_trace_id() or langfuse_trace_id,
                    trace_url=trace_url or langfuse_trace_url,
                    route=route[:240],
                    method=method[:16],
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
                    surface=surface[:32],
                    language_code=language_code[:16] if language_code else None,
                    state_code=state_code[:16] if state_code else None,
                    provider=provider[:64] if provider else None,
                    outcome=outcome[:32],
                    error_code=error_code[:96] if error_code else None,
                    safe_metadata=_safe_metadata(safe_metadata),
                    created_at=datetime.now(UTC),
                )
            )
    except Exception as exc:  # pragma: no cover - exercised by deployment failures
        log.warning("telemetry_write_failed", error=exc.__class__.__name__)


def make_audit_event(
    *,
    principal: AdminPrincipal,
    action: str,
    target_type: str,
    target_id: str = "",
    reason: str = "",
    safe_before: Mapping[str, Any] | None = None,
    safe_after: Mapping[str, Any] | None = None,
) -> AuditEvent:
    """Build an audit row for insertion in the same transaction as a change."""
    return AuditEvent(
        id=new_id("aud"),
        actor_id=principal.actor_id[:120],
        actor_role=principal.role[:32],
        action=action[:120],
        target_type=target_type[:80],
        target_id=target_id[:160],
        reason=reason[:500],
        safe_before=_safe_metadata(safe_before),
        safe_after=_safe_metadata(safe_after),
        request_id=request_id_var.get(),
        created_at=datetime.now(UTC),
    )
