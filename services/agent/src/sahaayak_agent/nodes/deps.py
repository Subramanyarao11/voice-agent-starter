"""Dependencies injected into graph nodes.

LangGraph nodes receive only the state, so everything else is bound at graph
construction time. Passing a session factory rather than a session keeps each
node's database work scoped to that node instead of holding a connection open
across model calls.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass

from sqlmodel import Session

from sahaayak_agent.retrieval import OpenAIRetrieval, RagUnavailable
from sahaayak_agent.understanding import Understanding
from sahaayak_common import get_logger, session_scope, settings

SessionFactory = Callable[[], AbstractContextManager[Session] | Iterator[Session]]
log = get_logger(__name__)


@dataclass(slots=True)
class GraphDeps:
    understanding: Understanding
    retrieval: OpenAIRetrieval | None = None
    session_factory: SessionFactory = session_scope

    @classmethod
    def build(cls, retrieval: OpenAIRetrieval | None = None) -> GraphDeps:
        if retrieval is None and settings.llm_enabled and settings.resolved_openai_vector_store_id:
            try:
                retrieval = OpenAIRetrieval()
            except RagUnavailable as exc:
                # The dialogue remains useful without informational RAG. The
                # node will return a local-language configuration fallback.
                log.warning("rag_not_available_for_dialogue", reason=str(exc))
        return cls(understanding=Understanding.build(), retrieval=retrieval)
