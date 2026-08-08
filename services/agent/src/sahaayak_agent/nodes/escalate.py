"""Deciding when to stop answering and fetch a human.

Escalation is treated as a feature rather than a failure path. The callers this
serves often have no other way to check an entitlement, so "I am not sure, let
me get someone who is" is a better outcome than a confident guess that costs
them a form fee or a wasted trip to an office.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_common import (
    EscalationTicket,
    get_logger,
    resolve_escalation_route,
    settings,
    ticket_id,
)
from sahaayak_contracts import AgentState, EscalationReason, Intent, MatchVerdict

log = get_logger(__name__)

# Two consecutive turns where nothing landed. A third attempt at the same
# misunderstanding is rarely the one that works.
MISUNDERSTANDING_LIMIT = 2


def _decide_reason(state: AgentState) -> EscalationReason | None:
    if state.intent is Intent.REQUEST_HUMAN:
        return EscalationReason.CALLER_REQUESTED

    if state.consecutive_misunderstandings >= MISUNDERSTANDING_LIMIT:
        return EscalationReason.REPEATED_MISUNDERSTANDING

    # Mid-conversation, with a question still pending, there is nothing to
    # escalate about yet.
    if state.pending_slot is not None:
        return None

    if state.domain is None:
        return None

    threshold = settings.escalation_confidence_threshold
    confident = [
        m
        for m in state.matches
        if m.verdict is MatchVerdict.ELIGIBLE and m.confidence >= threshold
    ]
    if confident:
        return None

    weak = [m for m in state.matches if m.verdict is MatchVerdict.ELIGIBLE]
    if weak:
        return EscalationReason.LOW_CONFIDENCE
    return EscalationReason.NO_MATCHES


async def assess_escalation(state: AgentState, deps: GraphDeps) -> dict:
    reason = _decide_reason(state)
    if reason is None:
        return {"needs_escalation": False, "escalation_reason": None}

    # A durable row rather than a webhook call: if the volunteer queue is down,
    # the request is still recorded and can be picked up later.
    try:
        now = datetime.now(UTC)
        with deps.session_factory() as session:
            route = resolve_escalation_route(
                state_code=state.state_code,
                domain=state.domain,
                slots=state.slots,
                db=session,
            )
            session.add(
                EscalationTicket(
                    id=ticket_id(),
                    session_id=state.session_id,
                    reason=reason.value,
                    caller_context={
                        "language_code": state.language_code,
                        "state_code": state.state_code,
                        "domain": state.domain.value if state.domain else None,
                        "slots": {k.value: v for k, v in state.slots.items()},
                    },
                    transcript_excerpt=state.transcript[:500],
                    sla_due_at=now + timedelta(hours=max(1, settings.escalation_sla_hours)),
                    department=route.department,
                    routing_location=route.routing_location,
                    routing_source=route.routing_source,
                    routing_directory_entry_id=route.directory_entry_id,
                    routing_source_url=route.source_url,
                    routing_verified_at=route.verified_at,
                    created_at=now,
                    updated_at=now,
                )
            )
    except Exception as exc:
        # Never let bookkeeping end a call. The caller still hears the offer.
        log.error("escalation_ticket_write_failed", error=str(exc), exc_info=True)

    log.info("escalating", session_id=state.session_id, reason=reason.value)
    return {"needs_escalation": True, "escalation_reason": reason}
