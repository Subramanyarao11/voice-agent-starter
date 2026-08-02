"""Score every candidate benefit, then decide whether one more question helps."""

from __future__ import annotations

from sahaayak_agent import matcher, repository
from sahaayak_agent.nodes.deps import GraphDeps
from sahaayak_common import get_logger, settings
from sahaayak_contracts import AgentState, MatchVerdict, VerificationStatus

log = get_logger(__name__)

# How many confirmed matches are worth reading out on a call. Past this, more
# questions cost the caller time without changing what they will act on.
ENOUGH_MATCHES = 3

# A hard ceiling on interrogation. Someone who has answered this many questions
# without a clean match is better served by a person.
MAX_QUESTIONS = 8


async def match(state: AgentState, deps: GraphDeps) -> dict:
    if state.domain is None:
        return {"matches": []}

    with deps.session_factory() as session:
        candidates = repository.load_candidates(
            session, domain=state.domain, state_code=state.state_code
        )
        results = [
            matcher.evaluate(
                repository.criteria_for(benefit),
                state.slots,
                benefit_id=benefit.id,
                benefit_name=benefit.name,
                domain=benefit.domain,
                benefit_state=benefit.state_code,
                verification_status=benefit.verification_status,
                source_title=benefit.source_title,
                source_document_url=benefit.source_document_url or benefit.source_url,
                verified_at=benefit.verified_at,
                last_verified_date=(
                    benefit.last_verified_date
                    if benefit.verification_status is VerificationStatus.HUMAN_VERIFIED
                    else None
                ),
            )
            for benefit in candidates
        ]

    ranked = matcher.rank(results)
    log.info(
        "matched_candidates",
        session_id=state.session_id,
        domain=state.domain.value,
        candidates=len(ranked),
        eligible=sum(1 for r in ranked if r.verdict is MatchVerdict.ELIGIBLE),
        undecided=sum(1 for r in ranked if r.verdict is MatchVerdict.INSUFFICIENT_INFO),
    )
    return {"matches": ranked}


async def choose_followup(state: AgentState, deps: GraphDeps) -> dict:
    """Pick the next question, or decide there is nothing worth asking.

    The question chosen is the one that would resolve the most undecided
    candidates, so the caller's effort goes where it changes the answer instead
    of down a fixed questionnaire.
    """
    confirmed = [
        m
        for m in state.matches
        if m.verdict is MatchVerdict.ELIGIBLE
        and m.confidence >= settings.escalation_confidence_threshold
    ]
    if len(confirmed) >= ENOUGH_MATCHES:
        log.info("stopping_questions", session_id=state.session_id, reason="enough_matches")
        return {"pending_slot": None}

    if state.turn_index >= MAX_QUESTIONS:
        log.info("stopping_questions", session_id=state.session_id, reason="question_limit")
        return {"pending_slot": None}

    choice = matcher.most_informative_slot(state.matches)
    if choice is None:
        return {"pending_slot": None}

    slot, resolves = choice
    log.info(
        "chose_followup_question",
        session_id=state.session_id,
        slot=slot.value,
        would_resolve=resolves,
    )
    return {"pending_slot": slot}
