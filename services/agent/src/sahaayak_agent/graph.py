"""Assembly of the dialogue graph.

    understand → gather ─┬─(needs a question / no domain yet)─→ assess_escalation
                         └─(ready to match)─→ match → choose_followup → assess_escalation
                                                                              ↓
                                                                           compose

No node knows what language the call is in. Understanding normalises speech
into typed slots on the way in and the composer renders from the per-language
catalog on the way out, so the reasoning in between is identical whether the
caller spoke Kannada, Hindi, or a mixture.
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from sahaayak_agent.nodes import (
    GraphDeps,
    answer_from_knowledge,
    assess_escalation,
    choose_followup,
    compose,
    gather,
    match,
    understand,
)
from sahaayak_agent.tracing import traced
from sahaayak_contracts import AgentState, Intent


def route_after_gather(state: AgentState) -> str:
    """Decide whether this turn can attempt a match or must ask first."""
    if state.intent is Intent.REQUEST_HUMAN:
        return "assess_escalation"
    if state.domain is None:
        return "assess_escalation"
    if state.pending_slot is not None:
        return "assess_escalation"
    return "match"


def _eligibility_phrasing(transcript: str) -> bool:
    text = transcript.lower()
    markers = (
        "eligib",
        "qualify",
        "am i ",
        "do i get",
        "can i get",
        "can i apply",
        "will i get",
        "do i qualify",
    )
    return any(marker in text for marker in markers)


def route_after_understand(state: AgentState) -> str:
    """Send pure informational questions to RAG; keep eligibility in the matcher.

    A turn that answers a pending slot remains in the structured dialogue even
    if the model labels it ``provide_info``. "Am I eligible for X?" must not
    skip the deterministic matcher — RAG explains sources, it does not decide
    eligibility.
    """
    if state.scope_blocked:
        return "compose"
    if state.answered_pending_slot:
        return "gather"

    if state.intent is Intent.ASK_HOW_TO_APPLY:
        return "answer_from_knowledge"

    # Mid eligibility dialogue, a named scheme is usually "check this one", not a
    # pure encyclopedia ask. Route those turns through the matcher.
    if state.intent is Intent.ASK_ABOUT_BENEFIT:
        if _eligibility_phrasing(state.transcript) or state.domain is not None:
            return "gather"
        return "answer_from_knowledge"

    if state.intent is Intent.PROVIDE_INFO and not _eligibility_phrasing(state.transcript):
        return "answer_from_knowledge"

    return "gather"


def build_graph(deps: GraphDeps | None = None):
    deps = deps or GraphDeps.build()

    graph = StateGraph(AgentState)
    graph.add_node("understand", traced("understand")(partial(understand, deps=deps)))
    graph.add_node(
        "answer_from_knowledge",
        traced("answer_from_knowledge")(partial(answer_from_knowledge, deps=deps)),
    )
    graph.add_node("gather", traced("gather")(partial(gather, deps=deps)))
    graph.add_node("match", traced("match")(partial(match, deps=deps)))
    graph.add_node(
        "choose_followup", traced("choose_followup")(partial(choose_followup, deps=deps))
    )
    graph.add_node(
        "assess_escalation", traced("assess_escalation")(partial(assess_escalation, deps=deps))
    )
    graph.add_node("compose", traced("compose")(partial(compose, deps=deps)))

    graph.set_entry_point("understand")
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {
            "answer_from_knowledge": "answer_from_knowledge",
            "gather": "gather",
            "compose": "compose",
        },
    )
    graph.add_edge("answer_from_knowledge", "compose")
    graph.add_conditional_edges(
        "gather",
        route_after_gather,
        {"match": "match", "assess_escalation": "assess_escalation"},
    )
    graph.add_edge("match", "choose_followup")
    graph.add_edge("choose_followup", "assess_escalation")
    graph.add_edge("assess_escalation", "compose")
    graph.add_edge("compose", END)

    return graph.compile()
