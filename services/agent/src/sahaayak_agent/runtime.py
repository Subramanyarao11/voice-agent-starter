"""Running one conversational turn, including durable memory.

The graph itself is stateless. This layer rehydrates a caller's profile before
the turn and writes it back afterwards, which is what turns a sequence of calls
into one continuing conversation: someone who rang last week is not asked their
age again.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sahaayak_agent.graph import build_graph
from sahaayak_agent.nodes import GraphDeps
from sahaayak_agent.tracing import (
    langfuse_turn,
    record_turn_metric,
    start_span,
    update_langfuse_observation,
)
from sahaayak_common import (
    ConversationTurnLog,
    UserSession,
    get_logger,
    settings,
    turn_id,
)
from sahaayak_common import (
    session_id as new_session_id,
)
from sahaayak_contracts import (
    AgentState,
    Domain,
    Intent,
    MatchSummary,
    MatchVerdict,
    SlotName,
    SlotValue,
    TurnResponse,
)

log = get_logger(__name__)


def _profile_to_slots(profile: dict) -> dict[SlotName, SlotValue]:
    """Rebuild typed slots from stored JSON, discarding anything unrecognised."""
    slots: dict[SlotName, SlotValue] = {}
    for key, value in (profile or {}).items():
        try:
            slots[SlotName(key)] = value
        except ValueError:
            log.debug("dropping_unknown_stored_slot", slot=key)
    return slots


def _slots_to_profile(slots: dict[SlotName, SlotValue]) -> dict:
    return {slot.value: value for slot, value in slots.items()}


def _restore_conversation(stored: dict) -> tuple[Domain | None, SlotName | None, int]:
    """Resume the dialogue where it left off.

    Restoring the pending question is what makes a bare "22" mean an age. Read
    in isolation it is just a number; it only becomes an answer because the
    agent remembers it asked how old the caller is.
    """
    stored = stored or {}

    domain: Domain | None = None
    try:
        domain = Domain(stored["domain"]) if stored.get("domain") else None
    except ValueError:
        log.debug("dropping_unknown_stored_domain", domain=stored.get("domain"))

    pending: SlotName | None = None
    try:
        pending = SlotName(stored["pending_slot"]) if stored.get("pending_slot") else None
    except ValueError:
        log.debug("dropping_unknown_pending_slot", slot=stored.get("pending_slot"))

    return domain, pending, int(stored.get("consecutive_misunderstandings", 0))


def _store_conversation(state: AgentState) -> dict:
    return {
        "domain": state.domain.value if state.domain else None,
        "pending_slot": state.pending_slot.value if state.pending_slot else None,
        "consecutive_misunderstandings": state.consecutive_misunderstandings,
    }


class AgentRuntime:
    def __init__(self, deps: GraphDeps | None = None) -> None:
        self.deps = deps or GraphDeps.build()
        self.graph = build_graph(self.deps)

    def get_or_create_session(
        self,
        caller_id: str,
        *,
        state_code: str | None = None,
        language_code: str | None = None,
    ) -> UserSession:
        with self.deps.session_factory() as db:
            existing = db.query(UserSession).filter_by(phone_or_session_id=caller_id).first()
            if existing:
                # A returning caller may have switched language or moved state.
                if language_code and existing.language_code != language_code:
                    existing.language_code = language_code
                if state_code and existing.state_code != state_code:
                    existing.state_code = state_code
                db.add(existing)
                db.flush()
                db.refresh(existing)
                return _detach(existing)

            created = UserSession(
                id=new_session_id(),
                phone_or_session_id=caller_id,
                state_code=state_code or settings.default_state,
                language_code=language_code or settings.default_language,
            )
            db.add(created)
            db.flush()
            db.refresh(created)
            return _detach(created)

    async def run_turn(
        self,
        *,
        caller_id: str,
        transcript: str,
        language_code: str | None = None,
        state_code: str | None = None,
    ) -> tuple[UserSession, AgentState]:
        session = self.get_or_create_session(
            caller_id, state_code=state_code, language_code=language_code
        )

        domain, pending_slot, misunderstandings = _restore_conversation(
            session.conversation_state
        )
        initial = AgentState(
            session_id=session.id,
            state_code=session.state_code,
            language_code=session.language_code,
            transcript=transcript,
            slots=_profile_to_slots(session.profile),
            domain=domain,
            pending_slot=pending_slot,
            consecutive_misunderstandings=misunderstandings,
            turn_index=session.turn_count,
        )

        started = time.perf_counter()
        with start_span(
            "conversation.turn",
            {
                "conversation.session_id": session.id,
                "conversation.language": session.language_code,
                "conversation.state": session.state_code,
                "conversation.turn_index": session.turn_count,
            },
        ) as otel_span:
            with langfuse_turn(
                session_id=session.id,
                metadata={
                    "language": session.language_code,
                    "state": session.state_code,
                    "turn_index": session.turn_count,
                },
            ) as langfuse_observation:
                try:
                    raw = await self.graph.ainvoke(initial)
                    final = AgentState.model_validate(raw)
                    self._persist(session, final)
                except Exception as exc:
                    if otel_span is not None:
                        otel_span.record_exception(exc)
                        otel_span.set_attribute("error.type", exc.__class__.__name__)
                    raise

                duration_ms = (time.perf_counter() - started) * 1000
                outcome = (
                    "escalated"
                    if final.needs_escalation
                    else "follow_up"
                    if final.pending_slot
                    else "no_match"
                    if not final.matches and not final.knowledge_answer
                    else "success"
                )
                safe_metadata = {
                    "language": final.language_code,
                    "state": final.state_code,
                    "intent": final.intent.value,
                    "outcome": outcome,
                    "match_count": len(final.matches),
                    "source_count": len(final.knowledge_sources),
                    "slot_names": ",".join(sorted(slot.value for slot in final.slots)),
                    "duration_ms": round(duration_ms, 2),
                }
                if otel_span is not None:
                    for key, value in safe_metadata.items():
                        otel_span.set_attribute(f"conversation.{key}", value)
                update_langfuse_observation(langfuse_observation, safe_metadata)
                record_turn_metric(
                    duration_ms,
                    surface="conversation",
                    language_code=final.language_code,
                    outcome=outcome,
                )
                return session, final

    def _persist(self, session: UserSession, state: AgentState) -> None:
        confirmed = [
            m.benefit_id
            for m in state.matches
            if m.verdict is MatchVerdict.ELIGIBLE
            and m.confidence >= settings.escalation_confidence_threshold
        ]

        with self.deps.session_factory() as db:
            row = db.get(UserSession, session.id)
            if row is None:
                return
            row.profile = _slots_to_profile(state.slots)
            row.conversation_state = _store_conversation(state)
            row.turn_count = state.turn_index
            row.last_contact_at = datetime.now(UTC)
            if confirmed:
                row.matched_benefit_ids = confirmed
            db.add(row)

            db.add(
                ConversationTurnLog(
                    id=turn_id(),
                    session_id=session.id,
                    turn_index=state.turn_index,
                    role="caller",
                    text=state.transcript,
                    intent=state.intent.value,
                    slots_after={k.value: v for k, v in state.slots.items()},
                )
            )
            db.add(
                ConversationTurnLog(
                    id=turn_id(),
                    session_id=session.id,
                    turn_index=state.turn_index,
                    role="agent",
                    text=state.response_text,
                    intent=state.intent.value,
                    slots_after={},
                )
            )


def _detach(row: UserSession) -> UserSession:
    """Copy a row out of its session so it stays readable after the commit."""
    return UserSession.model_validate(row.model_dump())


def to_response(session: UserSession, state: AgentState) -> TurnResponse:
    return TurnResponse(
        session_id=session.id,
        transcript=state.transcript,
        response_text=state.response_text,
        grounded_answer=state.knowledge_answer or None,
        sources=state.knowledge_sources,
        intent=state.intent or Intent.UNKNOWN,
        slots=state.slots,
        pending_slot=state.pending_slot,
        matches=[
            MatchSummary(
                benefit_id=m.benefit_id,
                benefit_name=m.benefit_name,
                domain=m.domain,
                verdict=m.verdict.value,
                confidence=m.confidence,
                reasons=_match_reasons(m),
                verification_status=m.verification_status,
                source_title=m.source_title,
                source_document_url=m.source_document_url,
                verified_at=m.verified_at,
                last_verified_date=m.last_verified_date,
                job_metadata=m.job_metadata,
            )
            for m in state.matches[:10]
        ],
        needs_escalation=state.needs_escalation,
        escalation_reason=state.escalation_reason,
    )


def _match_reasons(match) -> list[str]:
    """Expose pass/fail/unknown evidence to the result page.

    Previously an insufficient-information result could have an empty reasons
    list because neither a pass nor a fail existed yet. Naming unresolved
    requirements is what lets the UI explain why it is uncertain without
    exposing the caller's sensitive profile values.
    """
    reasons: list[str] = []
    for outcome in match.outcomes:
        if outcome.status.value == "pass":
            reasons.append("Meets: " + outcome.requirement)
        elif outcome.status.value == "fail":
            reasons.append("Does not meet: " + outcome.requirement)
        else:
            reasons.append("Still need to confirm: " + outcome.requirement)
    return reasons
