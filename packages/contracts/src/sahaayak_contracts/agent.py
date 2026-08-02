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

    matches: list[EligibilityMatchResult] = Field(default_factory=list)

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

    # A phone number in telephony, a browser-generated ID in the web demo.
    # Either way it is the key a returning caller is recognised by.
    caller_id: str
    text: str
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


class TurnResponse(BaseModel):
    session_id: str
    transcript: str
    response_text: str

    intent: Intent
    slots: dict[SlotName, SlotValue] = Field(default_factory=dict)
    pending_slot: SlotName | None = None

    matches: list[MatchSummary] = Field(default_factory=list)
    needs_escalation: bool = False
    escalation_reason: EscalationReason | None = None

    # Populated only by the voice endpoint, and only when TTS is configured.
    audio_base64: str | None = None
    audio_mime_type: str | None = None
