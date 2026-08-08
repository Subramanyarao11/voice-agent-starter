"""Answer informational turns from the persistent source corpus.

Retrieval is deliberately a separate graph lane. It can explain a source
document, but it never creates ``matches`` and therefore cannot turn a
machine-extracted sentence into an eligibility decision.
"""

from __future__ import annotations

from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_agent.retrieval import RagUnavailable
from sahaayak_common import BudgetError, get_logger
from sahaayak_contracts import AgentState

log = get_logger(__name__)


async def answer_from_knowledge(state: AgentState, deps: GraphDeps) -> dict:
    """Retrieve a concise source-grounded answer for an informational turn."""
    if deps.retrieval is None:
        return {"knowledge_error": "not_configured"}

    try:
        result = await deps.retrieval.answer(
            state.transcript,
            language_code=state.language_code,
            subject=state.session_id,
            state_code=state.state_code,
        )
    except (BudgetError, RagUnavailable) as exc:
        log.warning(
            "knowledge_answer_unavailable",
            session_id=state.session_id,
            reason=str(exc),
        )
        return {"knowledge_error": "unavailable"}

    if not result.answer.strip():
        return {
            "knowledge_sources": result.sources,
            "knowledge_error": "empty_answer",
        }

    log.info(
        "knowledge_answered",
        session_id=state.session_id,
        sources=len(result.sources),
    )
    return {
        "knowledge_answer": result.answer,
        "knowledge_sources": result.sources,
        "knowledge_error": None,
    }
