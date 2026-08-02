"""Database tables.

Language, state, and domain are rows and column values rather than branches in
code. Serving another language means inserting a `Language`; serving another
state means running the ingestion pipeline again with a different filter.
Neither requires touching the agent.
"""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Enum as SAEnum, Index
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlmodel import Field, SQLModel

from sahaayak_contracts import Domain


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_dict() -> Column:
    """A JSON object column that notices in-place mutation.

    Without `MutableDict`, assigning `session.profile["age"] = 22` leaves the
    ORM unaware anything changed and the update is silently dropped on commit.
    """
    return Column(MutableDict.as_mutable(JSON), nullable=False)


def json_list() -> Column:
    return Column(MutableList.as_mutable(JSON), nullable=False)


def enum_column(enum_type: type, **kwargs) -> Column:
    """Store an enum as plain VARCHAR.

    `native_enum=False` keeps new enum members from requiring a database
    migration, which matters because adding a domain is meant to be a data
    change rather than a schema change.
    """
    return Column(SAEnum(enum_type, native_enum=False, length=32), **kwargs)


class Language(SQLModel, table=True):
    __tablename__ = "language"

    code: str = Field(primary_key=True)  # "kn", "hi", "ta", "te", "mr"
    name: str
    native_name: str = ""

    stt_provider: str = "openai_whisper"
    stt_locale: str = ""
    tts_provider: str = "sarvam_bulbul"
    tts_locale: str = ""
    tts_voice_id: str = "anushka"

    is_active: bool = True


class State(SQLModel, table=True):
    __tablename__ = "state"

    code: str = Field(primary_key=True)  # "KA", "MH", "TN", ...
    name: str
    primary_language_code: str = Field(foreign_key="language.code")
    is_active: bool = True


class Benefit(SQLModel, table=True):
    """One scheme, scholarship, or job opening.

    A single table serves all three because they answer the same questions:
    who qualifies, what do they get, and how do they apply. Jobs simply leave
    the scheme-shaped eligibility fields unset.
    """

    __tablename__ = "benefit"
    __table_args__ = (
        # The matcher always narrows by domain and state before scoring, so
        # this composite index covers its only hot query.
        Index("ix_benefit_domain_state", "domain", "state_code"),
    )

    id: str = Field(primary_key=True)  # slug, e.g. "csss-cus"
    domain: Domain = Field(sa_column=enum_column(Domain, nullable=False, index=True))
    name: str
    # NULL means central / all-India rather than "unknown".
    state_code: str | None = Field(default=None, foreign_key="state.code", index=True)
    category: str = ""
    description: str = ""

    eligibility_initial: dict = Field(default_factory=dict, sa_column=json_dict())
    eligibility_renewal: dict | None = Field(
        default=None, sa_column=Column(MutableDict.as_mutable(JSON), nullable=True)
    )

    benefits_text: str = ""
    documents_required: list[str] = Field(default_factory=list, sa_column=json_list())
    application_process: str = ""

    source_url: str = ""
    last_verified_date: date = Field(default_factory=lambda: _utcnow().date())

    # Per-language voice-ready summaries, e.g. {"kn": "...", "hi": "..."}.
    # Pre-translated at ingestion so a call never waits on a translation.
    localized_summary: dict = Field(default_factory=dict, sa_column=json_dict())

    is_active: bool = True


class UserSession(SQLModel, table=True):
    """A caller's durable profile.

    This is what makes the agent long-running rather than one-shot: a caller
    who rang last week is not asked their age again, and unfinished tasks are
    still waiting when they call back.
    """

    __tablename__ = "user_session"

    id: str = Field(primary_key=True)
    phone_or_session_id: str = Field(index=True, unique=True)
    state_code: str = Field(foreign_key="state.code")
    language_code: str = Field(foreign_key="language.code")

    profile: dict = Field(default_factory=dict, sa_column=json_dict())
    open_tasks: list[dict] = Field(default_factory=list, sa_column=json_list())
    matched_benefit_ids: list[str] = Field(default_factory=list, sa_column=json_list())

    turn_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    last_contact_at: datetime = Field(default_factory=_utcnow)


class ConversationTurnLog(SQLModel, table=True):
    """Turn-by-turn transcript, kept for demo playback and quality review."""

    __tablename__ = "conversation_turn_log"

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    turn_index: int
    role: str  # "caller" | "agent"
    text: str
    intent: str = ""
    slots_after: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow)


class EscalationTicket(SQLModel, table=True):
    """A handoff to a human volunteer.

    Written whenever the agent would otherwise have to guess. Deliberately a
    durable row rather than a fire-and-forget webhook, so nothing is lost if
    the volunteer queue is down.
    """

    __tablename__ = "escalation_ticket"

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    reason: str
    caller_context: dict = Field(default_factory=dict, sa_column=json_dict())
    transcript_excerpt: str = ""
    status: str = Field(default="open", index=True)  # open | claimed | resolved
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
