"""
Core data model. Language, State, and Domain are all rows/enums, not code branches —
this is what lets us scale to 5 languages x 5 states x 3 domains by adding data,
not rewriting the agent. See spec-v2 section 5 (Extensibility).
"""
from datetime import UTC, date, datetime
from enum import Enum

from sqlmodel import JSON, Column, Field, SQLModel


class Domain(str, Enum):
    SCHEME = "scheme"
    SCHOLARSHIP = "scholarship"
    JOB = "job"


class Language(SQLModel, table=True):
    code: str = Field(primary_key=True)  # "kn", "hi", "ta", "te", "mr"
    name: str
    stt_provider: str = "openai_whisper"
    tts_provider: str = "sarvam_bulbul"
    tts_voice_id: str = ""


class State(SQLModel, table=True):
    code: str = Field(primary_key=True)  # "KA", "MH", "TN", ...
    name: str
    primary_language_code: str = Field(foreign_key="language.code")


class Benefit(SQLModel, table=True):
    """
    Unified record for schemes, scholarships, and jobs. `domain` distinguishes
    the type; `eligibility_initial` / `eligibility_renewal` follow the structured
    schema in spec-v2 section 4 — parsed from myScheme's free-text eligibility,
    NOT left as raw prose, so the agent can reason over it precisely.
    """
    id: str = Field(primary_key=True)  # slug, e.g. "csss-cus"
    domain: Domain
    name: str
    state_code: str | None = Field(default=None, foreign_key="state.code")  # null = central/all-India
    category: str  # e.g. "Education & Learning", "Housing", "Agriculture"
    description: str

    eligibility_initial: dict = Field(default_factory=dict, sa_column=Column(JSON))
    eligibility_renewal: dict | None = Field(default=None, sa_column=Column(JSON))

    benefits_text: str
    documents_required: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    application_process: str
    source_url: str
    last_verified_date: date

    # localized copy per language for voice responses: {"kn": "...", "hi": "..."}
    localized_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))


class UserSession(SQLModel, table=True):
    """
    Session memory — what makes this a "long-running agent" rather than a
    one-shot query tool. `profile` holds collected slots (age, income, category,
    etc.); `open_tasks` holds unresolved follow-ups the agent can bring up on a
    future call.
    """
    id: str = Field(primary_key=True)
    phone_or_session_id: str = Field(index=True)
    state_code: str = Field(foreign_key="state.code")
    language_code: str = Field(foreign_key="language.code")

    profile: dict = Field(default_factory=dict, sa_column=Column(JSON))
    open_tasks: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    matched_benefit_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_contact_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
