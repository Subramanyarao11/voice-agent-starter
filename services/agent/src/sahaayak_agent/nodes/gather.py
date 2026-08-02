"""Collect the minimum facts needed before matching is worth attempting.

Running the matcher against an empty profile would return every benefit as
"insufficient information", which tells the caller nothing and costs a turn. So
a small floor of questions is asked first, after which the matcher itself takes
over choosing what to ask next.
"""

from __future__ import annotations

from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_common import get_logger
from sahaayak_contracts import MINIMUM_SLOTS, SLOT_REGISTRY, AgentState

log = get_logger(__name__)


async def gather(state: AgentState, deps: GraphDeps) -> dict:
    if state.domain is None:
        return {"pending_slot": None}

    required = MINIMUM_SLOTS.get(state.domain, [])
    missing = [slot for slot in required if slot not in state.slots]
    if not missing:
        return {"pending_slot": None}

    # Ask in registry order rather than the order they happen to be listed.
    next_slot = min(missing, key=lambda slot: SLOT_REGISTRY[slot].priority)
    log.info(
        "gathering_minimum_slots",
        session_id=state.session_id,
        asking=next_slot.value,
        still_missing=[s.value for s in missing],
    )
    return {"pending_slot": next_slot}
