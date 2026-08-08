"""Conversation state and the request/response shapes at the service boundary.

`AgentState` is what flows between LangGraph nodes. It holds typed slots and
match results rather than accumulated prose, which is what lets the same graph
serve any language.
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from sahaayak_contracts.domain import Domain, Intent, VerificationStatus
from sahaayak_contracts.eligibility import EligibilityMatchResult
from sahaayak_contracts.retrieval import RetrievedSource
from sahaayak_contracts.slots import SlotName

SlotValue = int | float | str | bool


class ConversationTurn(BaseModel):
    role: Literal["caller", "agent"]
    text: str


class EscalationReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    CALLER_REQUESTED = "caller_requested"
    REPEATED_MISUNDERSTANDING = "repeated_misunderstanding"
    NO_MATCHES = "no_matches"


class AgentState(BaseModel):
    session_id: str
    state_code: str
    language_code: str

    # Latest caller utterance, already transcribed. The graph never sees audio.
    transcript: str = ""

    intent: Intent = Intent.UNKNOWN
    domain: Domain | None = None

    slots: dict[SlotName, SlotValue] = Field(default_factory=dict)
    # Filled on this turn specifically, so the composer can acknowledge what it
    # just heard ("got it, age 22") instead of repeating the whole profile.
    newly_filled: list[SlotName] = Field(default_factory=list)
    # The slot the agent is asking for on this turn, if any.
    pending_slot: SlotName | None = None
    # Whether the previous turn had an unanswered slot question. This keeps
    # an answer such as "22" in the structured lane even if understanding also
    # labels it as general information.
    answered_pending_slot: bool = False

    matches: list[EligibilityMatchResult] = Field(default_factory=list)

    # Informational questions may be answered from the hosted source corpus.
    # These fields never participate in eligibility matching.
    knowledge_answer: str = ""
    knowledge_sources: list[RetrievedSource] = Field(default_factory=list)
    knowledge_error: str | None = None

    response_text: str = ""
    needs_escalation: bool = False
    escalation_reason: EscalationReason | None = None

    turn_index: int = 0
    history: list[ConversationTurn] = Field(default_factory=list)
    # Consecutive turns where nothing could be understood. Two in a row is the
    # point at which continuing to guess wastes the caller's time.
    consecutive_misunderstandings: int = 0


class TurnRequest(BaseModel):
    """A text-mode turn. The voice endpoint builds this after transcription."""

    # Identity comes from the server-issued browser session bearer token. A
    # caller identifier must never be accepted from the request body.
    text: str = Field(min_length=1, max_length=2_000)
    language_code: str | None = None
    state_code: str | None = None


class MatchSummary(BaseModel):
    """A match flattened for the API, without the full criterion trace."""

    benefit_id: str
    benefit_name: str
    domain: Domain
    verdict: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.ILLUSTRATIVE
    source_title: str = ""
    source_document_url: str = ""
    verified_at: datetime | None = None
    last_verified_date: date | None = None
    job_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TurnResponse(BaseModel):
    session_id: str
    transcript: str
    response_text: str
    # The spoken/display answer is citation-marker-free. The grounded answer
    # preserves the model's [Source N] markers for clients that want to render
    # inline citations alongside the source cards.
    grounded_answer: str | None = None
    sources: list[RetrievedSource] = Field(default_factory=list)

    intent: Intent
    slots: dict[SlotName, SlotValue] = Field(default_factory=dict)
    pending_slot: SlotName | None = None

    matches: list[MatchSummary] = Field(default_factory=list)
    needs_escalation: bool = False
    escalation_reason: EscalationReason | None = None

    # Populated only by the voice endpoint, and only when TTS is configured.
    audio_base64: str | None = None
    audio_mime_type: str | None = None
