"""First node of every turn: work out what the caller just said."""

from __future__ import annotations

from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_agent.understanding import rules
from sahaayak_common import get_logger
from sahaayak_contracts import AgentState, ConversationTurn, Intent

log = get_logger(__name__)


async def understand(state: AgentState, deps: GraphDeps) -> dict:
    answered_pending_slot = state.pending_slot is not None
    result = await deps.understanding.understand(
        state.transcript,
        language_code=state.language_code,
        pending_slot=state.pending_slot,
        known_slots=state.slots,
    )

    # Only count a slot as newly filled if the value actually changed, so a
    # caller repeating themselves does not get "got it" a second time.
    newly_filled = [
        slot for slot, value in result.slots.items() if state.slots.get(slot) != value
    ]
    slots = {**state.slots, **result.slots}

    understood = bool(result.slots) or result.intent is not Intent.UNKNOWN
    misunderstandings = 0 if understood else state.consecutive_misunderstandings + 1

    log.info(
        "understood_turn",
        session_id=state.session_id,
        intent=result.intent.value,
        source=result.source,
        newly_filled=[s.value for s in newly_filled],
        confidence=result.confidence,
    )

    return {
        "intent": result.intent,
        "domain": (
            state.domain
            if result.scope_blocked
            else rules.infer_domain(result.intent, state.domain)
        ),
        "slots": slots,
        "newly_filled": newly_filled,
        # Cleared here and re-decided downstream, so a question is never left
        # pending once the caller has answered it.
        "pending_slot": None,
        "answered_pending_slot": answered_pending_slot,
        "consecutive_misunderstandings": misunderstandings,
        "scope_blocked": result.scope_blocked,
        "history": [*state.history, ConversationTurn(role="caller", text=state.transcript)],
        "turn_index": state.turn_index + 1,
    }
