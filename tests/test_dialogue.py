"""End-to-end conversations through the graph, with no model and no network.

These are the tests that would catch a regression a caller would actually
notice: a question that never gets asked, an answer that is not remembered, or
a rejection delivered without grounds.
"""

from __future__ import annotations

import pytest

from sahaayak_agent.prompts import get_catalog
from sahaayak_contracts import EscalationReason, Intent, MatchVerdict, SlotName


async def say(runtime, caller_id, text, language="en", state="KA"):
    _, agent_state = await runtime.run_turn(
        caller_id=caller_id, transcript=text, language_code=language, state_code=state
    )
    return agent_state


@pytest.mark.asyncio
async def test_scholarship_conversation_reaches_a_verdict(runtime, caller_id):
    for utterance in [
        "I need a scholarship",
        "I am 22",
        "2 lakh rupees",
        "regular degree college",
        "SC",
    ]:
        state = await say(runtime, caller_id, utterance)

    while state.pending_slot is not None:
        state = await say(runtime, caller_id, "yes")

    eligible = [m for m in state.matches if m.verdict is MatchVerdict.ELIGIBLE]
    assert eligible, "a 22-year-old SC student on 2 lakh should qualify for something"
    assert state.response_text


@pytest.mark.asyncio
async def test_a_pending_question_survives_to_the_next_turn(runtime, caller_id):
    """A bare "22" is only an age because the agent remembers what it asked."""
    first = await say(runtime, caller_id, "I need a scholarship")
    assert first.pending_slot is SlotName.AGE

    second = await say(runtime, caller_id, "22")
    assert second.slots[SlotName.AGE] == 22


@pytest.mark.asyncio
async def test_the_caller_is_never_asked_the_same_thing_twice(runtime, caller_id):
    asked: list[SlotName] = []
    answers = {
        SlotName.AGE: "22",
        SlotName.ANNUAL_FAMILY_INCOME: "2 lakh",
        SlotName.EDUCATION_LEVEL: "degree",
        SlotName.SOCIAL_CATEGORY: "SC",
        SlotName.GENDER: "female",
        SlotName.ENROLLMENT_MODE: "regular",
        SlotName.DISABILITY: "no",
        SlotName.STATE_RESIDENCY: "yes",
        SlotName.OCCUPATION: "student",
    }

    state = await say(runtime, caller_id, "I need a scholarship")
    for _ in range(10):
        if state.pending_slot is None:
            break
        assert state.pending_slot not in asked, f"asked {state.pending_slot} twice"
        asked.append(state.pending_slot)
        state = await say(runtime, caller_id, answers.get(state.pending_slot, "yes"))

    assert len(asked) >= 3


@pytest.mark.asyncio
async def test_volunteered_details_skip_their_questions(runtime, caller_id):
    """Someone who introduces themselves fully should not be re-interviewed."""
    state = await say(
        runtime, caller_id, "I am a 22 year old SC girl in regular degree college"
    )
    assert state.slots[SlotName.AGE] == 22
    assert state.slots[SlotName.SOCIAL_CATEGORY] == "SC"
    assert state.slots[SlotName.EDUCATION_LEVEL] == "UG"
    assert state.pending_slot not in {
        SlotName.AGE,
        SlotName.SOCIAL_CATEGORY,
        SlotName.EDUCATION_LEVEL,
    }


@pytest.mark.asyncio
async def test_a_returning_caller_keeps_their_profile(runtime, caller_id):
    await say(runtime, caller_id, "I need a scholarship")
    await say(runtime, caller_id, "22")

    # A fresh runtime stands in for a later call hitting a restarted process.
    from sahaayak_agent import AgentRuntime

    later = await say(AgentRuntime(), caller_id, "hello again")
    assert later.slots[SlotName.AGE] == 22


@pytest.mark.asyncio
async def test_asking_for_a_person_escalates_immediately(runtime, caller_id):
    state = await say(runtime, caller_id, "I want to talk to a person")
    assert state.intent is Intent.REQUEST_HUMAN
    assert state.escalation_reason is EscalationReason.CALLER_REQUESTED
    assert state.response_text == get_catalog("en").render("escalation_confirmed")


@pytest.mark.asyncio
async def test_no_matches_offers_a_human_rather_than_stopping(runtime, caller_id):
    for utterance in ["I need a scholarship", "I am 65", "50 lakh", "PhD"]:
        state = await say(runtime, caller_id, utterance)

    assert state.needs_escalation
    assert state.escalation_reason in {
        EscalationReason.NO_MATCHES,
        EscalationReason.LOW_CONFIDENCE,
    }
    if state.matches:
        assert get_catalog("en").render(
            "related_options", count=len(state.matches)
        ) in state.response_text
        assert get_catalog("en").render("no_matches") not in state.response_text


@pytest.mark.asyncio
async def test_repeated_misunderstanding_hands_over_to_a_human(runtime, caller_id):
    await say(runtime, caller_id, "I need a scholarship")
    await say(runtime, caller_id, "%%%%")
    state = await say(runtime, caller_id, "@@@@")
    assert state.escalation_reason is EscalationReason.REPEATED_MISUNDERSTANDING


@pytest.mark.asyncio
async def test_misunderstanding_repeats_the_outstanding_question(runtime, caller_id):
    """Apologising alone leaves the caller guessing at what was wanted."""
    await say(runtime, caller_id, "I need a scholarship")
    state = await say(runtime, caller_id, "%%%%")

    catalog = get_catalog("en")
    assert catalog.render("didnt_understand") in state.response_text
    assert catalog.render("ask_age") in state.response_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "utterances"),
    [
        ("kn", ["ವಿದ್ಯಾರ್ಥಿವೇತನ ಬೇಕು", "20", "1 ಲಕ್ಷ", "ಪದವಿ", "ಎಸ್ ಸಿ"]),
        ("hi", ["मुझे छात्रवृत्ति चाहिए", "20", "1 लाख", "स्नातक", "एससी"]),
    ],
)
async def test_the_same_conversation_works_in_every_language(
    runtime, caller_id, language, utterances
):
    """The graph is language-agnostic, so identical facts must reach identical
    slots regardless of the language they arrived in."""
    for utterance in utterances:
        state = await say(runtime, f"{caller_id}-{language}", utterance, language=language)

    assert state.slots[SlotName.AGE] == 20
    assert state.slots[SlotName.ANNUAL_FAMILY_INCOME] == 100_000
    assert state.slots[SlotName.EDUCATION_LEVEL] == "UG"
    assert state.slots[SlotName.SOCIAL_CATEGORY] == "SC"
    # The reply must be in the caller's language, not the reference English.
    assert state.response_text
    assert state.response_text != get_catalog("en").render("ask_age")


@pytest.mark.asyncio
async def test_a_rejection_comes_with_its_grounds(runtime, caller_id):
    for utterance in ["I need a scholarship", "I am 40", "9 lakh", "PhD"]:
        state = await say(runtime, caller_id, utterance)

    rejected = [m for m in state.matches if m.verdict is MatchVerdict.NOT_ELIGIBLE]
    assert rejected
    assert all(match.failed for match in rejected)


@pytest.mark.asyncio
async def test_eligibility_question_keeps_asking_instead_of_dead_ending(runtime, caller_id):
    """Income + category alone is not enough for a confirmed match — keep asking."""
    for utterance in [
        "I need a scholarship",
        "22",
        "2 lakh",
        "degree",
        "SC",
    ]:
        state = await say(runtime, caller_id, utterance)

    assert state.pending_slot is not None
    assert not state.needs_escalation
    assert get_catalog("en").render("escalation_offer") not in state.response_text

    state = await say(
        runtime, caller_id, "am I eligible for the Karnataka Vidyasiri Scholarship"
    )
    assert state.knowledge_answer == ""
    assert state.pending_slot is not None or any(
        m.verdict is MatchVerdict.ELIGIBLE for m in state.matches
    )
