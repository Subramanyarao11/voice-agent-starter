"""
Agent graph. Nodes are language-agnostic — they operate on structured slots
and the EligibilityCriteria schema, not raw text in a specific language. The
voice layer (services/voice.py) handles language in/out at the edges; this
graph never needs to know it's Kannada vs Hindi.

Wire each node through Langfuse's @observe decorator once tracing is set up
(see spec-v2 section 2 — this is the "show judges the reasoning trace" demo
asset, don't skip it).
"""
from enum import Enum
from typing import Optional

from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from app.schemas.eligibility import EligibilityMatchResult


class Intent(str, Enum):
    SCHEME = "scheme"
    SCHOLARSHIP = "scholarship"
    JOB = "job"
    UNKNOWN = "unknown"


class AgentState(BaseModel):
    session_id: str
    state_code: str
    language_code: str
    transcript: str = ""              # latest user utterance (post-STT)
    intent: Intent = Intent.UNKNOWN
    collected_slots: dict = {}        # age, income, category, etc.
    missing_slots: list[str] = []
    matches: list[EligibilityMatchResult] = []
    response_text: str = ""           # composed reply (pre-TTS)
    needs_escalation: bool = False


def detect_intent(state: AgentState) -> AgentState:
    # TODO: LLM call classifying transcript into Intent. Keep this cheap/fast —
    # it runs on every turn.
    return state


def slot_filling(state: AgentState) -> AgentState:
    # TODO: given intent + collected_slots so far, determine what's still
    # missing (age, income, category, ...) and either ask the next question
    # or proceed to matching if nothing's missing.
    return state


def eligibility_match(state: AgentState) -> AgentState:
    # TODO: query Benefit table filtered by domain + state_code, run
    # collected_slots against each Benefit.eligibility_initial, populate
    # state.matches with EligibilityMatchResult (including confidence score).
    return state


def compose_response(state: AgentState) -> AgentState:
    # TODO: turn state.matches (or the next missing-slot question) into
    # state.response_text, using Benefit.localized_summary[language_code]
    # where available instead of raw English text run through translation.
    if any(m.confidence < 0.7 for m in state.matches):
        state.needs_escalation = True
    return state


def route_after_slot_filling(state: AgentState) -> str:
    return "eligibility_match" if not state.missing_slots else "compose_response"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("slot_filling", slot_filling)
    graph.add_node("eligibility_match", eligibility_match)
    graph.add_node("compose_response", compose_response)

    graph.set_entry_point("detect_intent")
    graph.add_edge("detect_intent", "slot_filling")
    graph.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling,
        {"eligibility_match": "eligibility_match", "compose_response": "compose_response"},
    )
    graph.add_edge("eligibility_match", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()


agent_graph = build_graph()
