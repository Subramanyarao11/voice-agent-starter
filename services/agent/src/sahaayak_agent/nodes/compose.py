"""Render the reply.

Composition is template assembly from the per-language catalog, not free
generation. Two reasons: a model writing vernacular prose on every turn adds
latency and cost to a phone call, and more importantly the eligibility verdict
has already been decided deterministically — letting a model rephrase it is an
opportunity to contradict it.
"""

from __future__ import annotations

import re

from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_agent.prompts import get_catalog
from sahaayak_agent.repository import load_briefs
from sahaayak_common import State, get_logger, settings
from sahaayak_contracts import (
    SLOT_REGISTRY,
    AgentState,
    ConversationTurn,
    EscalationReason,
    Intent,
    MatchVerdict,
    SlotName,
)

log = get_logger(__name__)

# Three is about as many options as a listener retains from speech alone.
MAX_SPOKEN_RESULTS = 3
_SOURCE_MARKER = re.compile(r"\s*\[Source\s+\d+\]", re.IGNORECASE)


def _join(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


async def compose(state: AgentState, deps: GraphDeps) -> dict:
    catalog = get_catalog(state.language_code)
    parts: list[str] = []

    if state.knowledge_answer:
        # Source markers are preserved in ``grounded_answer`` for visual
        # clients, but should not be read aloud by Sarvam or another TTS.
        return _finish(
            state,
            [_SOURCE_MARKER.sub("", state.knowledge_answer).strip()],
        )

    if state.knowledge_error:
        return _finish(state, [catalog.render("knowledge_unavailable")])

    if state.turn_index <= 1 and state.intent is Intent.GREETING:
        parts.append(catalog.render("greeting"))
        return _finish(state, parts)

    if state.consecutive_misunderstandings > 0 and not state.needs_escalation:
        # Apologising alone leaves the caller guessing at what was wanted, so
        # the outstanding question is put again alongside it.
        parts.append(catalog.render("didnt_understand"))
        if state.pending_slot is not None:
            parts.append(_render_question(state, catalog, deps))
        return _finish(state, parts)

    if state.newly_filled:
        parts.append(catalog.render("acknowledge"))

    if state.escalation_reason is EscalationReason.CALLER_REQUESTED:
        parts.append(catalog.render("escalation_confirmed"))
        return _finish(state, parts)

    if state.pending_slot is not None:
        parts.append(_render_question(state, catalog, deps))
    elif state.domain is None:
        parts.append(catalog.render("ask_intent"))
    else:
        parts.extend(_render_results(state, catalog, deps))

    if state.needs_escalation:
        parts.append(catalog.render("escalation_offer"))

    return _finish(state, parts)


def _render_question(state: AgentState, catalog, deps: GraphDeps) -> str:
    slot = state.pending_slot
    spec = SLOT_REGISTRY[slot]  # type: ignore[index]

    params: dict[str, object] = {}
    if slot is SlotName.STATE_RESIDENCY:
        params["state"] = _state_name(state.state_code, deps)
    return catalog.render(spec.prompt_key, **params)


def _render_results(state: AgentState, catalog, deps: GraphDeps) -> list[str]:
    threshold = settings.escalation_confidence_threshold
    confident = [
        m
        for m in state.matches
        if m.verdict is MatchVerdict.ELIGIBLE and m.confidence >= threshold
    ][:MAX_SPOKEN_RESULTS]

    if not confident:
        return [catalog.render("no_matches")]

    with deps.session_factory() as session:
        details = load_briefs(
            session, [m.benefit_id for m in confident], state.language_code
        )

    parts = [
        catalog.render("results_intro_one")
        if len(confident) == 1
        else catalog.render("results_intro", count=len(confident))
    ]

    for result in confident:
        brief = details.get(result.benefit_id)
        parts.append(
            catalog.render(
                "eligible_item",
                name=result.benefit_name,
                summary=brief.summary if brief else "",
            )
        )
        # One caveat, not all of them: unverifiable conditions read aloud in
        # bulk turn an answer into a disclaimer.
        if result.caveats:
            parts.append(catalog.render("caveat", caveat=result.caveats[0]))

    # Application details for the top result only. Reading the steps and
    # document list for three schemes in a row is unusable over the phone.
    top = details.get(confident[0].benefit_id)
    if top and top.application_process:
        parts.append(catalog.render("how_to_apply", process=top.application_process))
    if top and top.documents_required:
        parts.append(
            catalog.render("documents_needed", documents=", ".join(top.documents_required))
        )

    return parts


def _state_name(state_code: str, deps: GraphDeps) -> str:
    with deps.session_factory() as session:
        row = session.get(State, state_code)
        return row.name if row else state_code


def _finish(state: AgentState, parts: list[str]) -> dict:
    text = _join(parts)
    return {
        "response_text": text,
        "history": [*state.history, ConversationTurn(role="agent", text=text)],
    }
