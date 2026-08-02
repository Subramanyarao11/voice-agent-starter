"""Tests for the shared text/voice graph's source-grounded information lane."""

from __future__ import annotations

import pytest

from sahaayak_agent import AgentRuntime, GraphDeps, Understanding, to_response
from sahaayak_contracts import RagAnswerResponse, RetrievedSource, SlotName


class FakeRetrieval:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def answer(
        self, query: str, *, language_code: str | None = None, **_
    ) -> RagAnswerResponse:
        self.calls.append((query, language_code))
        return RagAnswerResponse(
            query=query,
            answer="Source-grounded answer [Source 1].",
            sources=[
                RetrievedSource(
                    source_id="benefit-1",
                    filename="benefit-1.txt",
                    score=0.9,
                    excerpt="A supporting excerpt.",
                    source_url="https://example.test/benefit-1",
                )
            ],
        )


@pytest.mark.asyncio
async def test_informational_turn_uses_rag_without_creating_eligibility_matches(
    seeded, caller_id
):
    retrieval = FakeRetrieval()
    runtime = AgentRuntime(
        deps=GraphDeps(understanding=Understanding(), retrieval=retrieval)
    )

    session, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript="tell me about this benefit",
        language_code="kn",
        state_code="KA",
    )

    response = to_response(session, state)
    assert retrieval.calls == [("tell me about this benefit", "kn")]
    assert state.matches == []
    assert state.pending_slot is None
    assert response.response_text == "Source-grounded answer."
    assert response.grounded_answer == "Source-grounded answer [Source 1]."
    assert response.sources[0].source_url == "https://example.test/benefit-1"


@pytest.mark.asyncio
async def test_missing_rag_configuration_returns_a_localized_text_fallback(seeded, caller_id):
    runtime = AgentRuntime(deps=GraphDeps(understanding=Understanding()))

    _, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript="tell me about this benefit",
        language_code="kn",
        state_code="KA",
    )

    assert state.knowledge_sources == []
    assert "ಮೂಲ ದಾಖಲೆಗಳನ್ನು" in state.response_text


@pytest.mark.asyncio
async def test_answer_to_pending_slot_stays_in_structured_dialogue(seeded, caller_id):
    retrieval = FakeRetrieval()
    runtime = AgentRuntime(
        deps=GraphDeps(understanding=Understanding(), retrieval=retrieval)
    )

    await runtime.run_turn(
        caller_id=caller_id,
        transcript="I need a scholarship",
        language_code="en",
        state_code="KA",
    )
    _, state = await runtime.run_turn(
        caller_id=caller_id,
        transcript="22",
        language_code="en",
        state_code="KA",
    )

    assert retrieval.calls == []
    assert state.slots[SlotName.AGE] == 22
