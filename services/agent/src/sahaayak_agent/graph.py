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


def build_graph(deps: GraphDeps | None = None):
    deps = deps or GraphDeps.build()

    graph = StateGraph(AgentState)
    graph.add_node("understand", traced("understand")(partial(understand, deps=deps)))
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
    graph.add_edge("understand", "gather")
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
