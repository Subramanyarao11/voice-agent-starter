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

from sahaayak_agent.understanding import Understanding
from sahaayak_common import session_scope

SessionFactory = Callable[[], AbstractContextManager[Session] | Iterator[Session]]


@dataclass(slots=True)
class GraphDeps:
    understanding: Understanding
    session_factory: SessionFactory = session_scope

    @classmethod
    def build(cls) -> GraphDeps:
        return cls(understanding=Understanding.build())
