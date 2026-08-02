"""Running one conversational turn, including durable memory.

The graph itself is stateless. This layer rehydrates a caller's profile before
the turn and writes it back afterwards, which is what turns a sequence of calls
into one continuing conversation: someone who rang last week is not asked their
age again.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sahaayak_agent.graph import build_graph
from sahaayak_agent.nodes import GraphDeps
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

        raw = await self.graph.ainvoke(initial)
        final = AgentState.model_validate(raw)

        self._persist(session, final)
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
                reasons=[o.requirement for o in m.passed] or [o.requirement for o in m.failed],
                verification_status=m.verification_status,
                source_title=m.source_title,
                source_document_url=m.source_document_url,
                verified_at=m.verified_at,
                last_verified_date=m.last_verified_date,
            )
            for m in state.matches[:10]
        ],
        needs_escalation=state.needs_escalation,
        escalation_reason=state.escalation_reason,
    )
