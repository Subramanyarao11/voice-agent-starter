"""Database tables.

Language, state, and domain are rows and column values rather than branches in
code. Serving another language means inserting a `Language`; serving another
state means running the ingestion pipeline again with a different filter.
Neither requires touching the agent.
"""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlmodel import Field, SQLModel

from sahaayak_contracts import Domain, VerificationStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
    change rather than a schema change. `values_callable` is explicit because
    SQLAlchemy otherwise stores Python enum member names (``SCHEME``) while
    the API and contracts use the stable wire values (``scheme``).
    """
    return Column(
        SAEnum(
            enum_type,
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        **kwargs,
    )


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


class LanguageReadinessReview(SQLModel, table=True):
    """Release evidence required before an expansion language is enabled."""

    __tablename__ = "language_readiness_review"

    language_code: str = Field(primary_key=True, foreign_key="language.code")
    native_speaker_status: str = "pending"  # pending | approved | rejected
    interface_status: str = "pending"
    prompt_status: str = "pending"
    content_status: str = "pending"
    understanding_status: str = "pending"
    voice_status: str = "pending"
    accessibility_status: str = "pending"
    evidence_url: str = ""
    review_notes: str = ""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    activated_at: datetime | None = None
    updated_at: datetime = Field(default_factory=_utcnow)


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

    # `source_url` and `last_verified_date` are retained for compatibility with
    # the first ingestion pass. New data should use the explicit provenance
    # fields below; a date alone never makes a row verified.
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.ILLUSTRATIVE,
        sa_column=enum_column(VerificationStatus, nullable=False, index=True),
    )
    source_title: str = ""
    source_document_url: str = ""
    source_excerpt: str | None = None
    source_content_hash: str | None = Field(default=None, index=True)
    automated_review: dict = Field(default_factory=dict, sa_column=json_dict())
    verified_by: str | None = None
    verified_at: datetime | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    # Per-language voice-ready summaries, e.g. {"kn": "...", "hi": "..."}.
    # Pre-translated at ingestion so a call never waits on a translation.
    localized_summary: dict = Field(default_factory=dict, sa_column=json_dict())

    # Job postings need a few fields that do not belong in generic eligibility
    # criteria: vacancy reference, employer, deadline, pay/employment details,
    # and the official application endpoint. Keeping these in one namespaced
    # JSON object lets other domains evolve without a column per domain while
    # preserving the same provenance/review lifecycle.
    job_metadata: dict | None = Field(
        default=None,
        sa_column=Column(MutableDict.as_mutable(JSON), nullable=True),
    )

    # Monotonic public-content revision. A revision is written to
    # `benefit_version` before/after every workforce edit, review decision, or
    # rollback. Keeping the counter on the current row avoids relying on
    # timestamps for concurrency-sensitive rollback UX.
    content_revision: int = 0
    is_active: bool = True


class BenefitVersion(SQLModel, table=True):
    """Immutable public snapshot of one benefit governance state.

    The snapshot intentionally contains only benefit/provenance fields. It
    never includes a caller profile, transcript, contact destination, or other
    private session data. A rollback creates a new version rather than
    deleting history.
    """

    __tablename__ = "benefit_version"
    __table_args__ = (
        Index(
            "ix_benefit_version_benefit_version",
            "benefit_id",
            "version",
            unique=True,
        ),
        Index("ix_benefit_version_benefit_created", "benefit_id", "created_at"),
    )

    id: str = Field(primary_key=True)
    benefit_id: str = Field(foreign_key="benefit.id", index=True)
    version: int = Field(index=True)
    action: str = Field(index=True)  # baseline | edit | review | rollback | import
    actor_id: str = Field(index=True)
    actor_role: str = ""
    reason: str = ""
    snapshot: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class SourceFreshnessAlert(SQLModel, table=True):
    """Deduplicated, actionable alert for a stale or incomplete source row."""

    __tablename__ = "source_freshness_alert"
    __table_args__ = (
        Index("ix_source_freshness_alert_status_seen", "status", "last_seen_at"),
        Index("ix_source_freshness_alert_dataset_status", "dataset", "status"),
    )

    id: str = Field(primary_key=True)
    alert_key: str = Field(index=True, unique=True)
    benefit_id: str | None = Field(default=None, foreign_key="benefit.id", index=True)
    dataset: str = Field(index=True)
    alert_type: str = Field(index=True)  # stale_source | missing_source | expired
    severity: str = "warning"  # warning | critical
    status: str = Field(default="open", index=True)  # open | acknowledged | resolved
    message: str = ""
    first_seen_at: datetime = Field(default_factory=_utcnow, index=True)
    last_seen_at: datetime = Field(default_factory=_utcnow, index=True)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())


class UserSession(SQLModel, table=True):
    """A caller's durable profile.

    This is what makes the agent long-running rather than one-shot: a caller
    who rang last week is not asked their age again, and unfinished tasks are
    still waiting when they call back.
    """

    __tablename__ = "user_session"

    id: str = Field(primary_key=True)
    phone_or_session_id: str = Field(index=True, unique=True)
    # Browser sessions use a one-time opaque bearer token whose hash is stored
    # here. Legacy telephony rows may leave this null until that channel gets
    # its own verified webhook identity.
    access_token_hash: str | None = Field(default=None, index=True, unique=True)
    auth_mode: str = Field(default="guest", index=True)  # guest | telephony | legacy
    expires_at: datetime | None = Field(default=None, index=True)
    state_code: str = Field(foreign_key="state.code")
    language_code: str = Field(foreign_key="language.code")

    # Durable facts about the caller: age, income, category. These outlive any
    # single call and are what stop a returning caller being re-interviewed.
    profile: dict = Field(default_factory=dict, sa_column=json_dict())

    # Where the conversation itself had got to — the domain being discussed and
    # the question awaiting an answer. Kept apart from `profile` because it is
    # dialogue bookkeeping, not something true about the caller.
    conversation_state: dict = Field(default_factory=dict, sa_column=json_dict())

    open_tasks: list[dict] = Field(default_factory=list, sa_column=json_list())
    matched_benefit_ids: list[str] = Field(default_factory=list, sa_column=json_list())

    turn_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    last_contact_at: datetime = Field(default_factory=_utcnow)


class SavedBenefit(SQLModel, table=True):
    """A caller's private shortlist of benefits.

    The row is deliberately keyed to the server-owned session rather than a
    browser-controlled identifier. Guest users can save items without creating
    an account, and deleting the guest session removes the relationship with
    the rest of that session's data.
    """

    __tablename__ = "saved_benefit"
    __table_args__ = (
        Index("ix_saved_benefit_session_benefit", "session_id", "benefit_id", unique=True),
    )

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    benefit_id: str = Field(foreign_key="benefit.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class ApplicationTask(SQLModel, table=True):
    """A private, durable checklist item for one saved benefit."""

    __tablename__ = "application_task"
    __table_args__ = (
        Index(
            "ix_application_task_session_benefit_status",
            "session_id",
            "benefit_id",
            "status",
        ),
        Index(
            "ix_application_task_session_benefit_title",
            "session_id",
            "benefit_id",
            "kind",
            "title",
            unique=True,
        ),
    )

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    benefit_id: str = Field(foreign_key="benefit.id", index=True)
    kind: str = Field(index=True)  # document | application_step
    title: str
    description: str = ""
    position: int = 0
    status: str = Field(default="pending", index=True)  # pending | completed | skipped
    due_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = None
    source_revision: int = 0
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)


class BenefitIssueReport(SQLModel, table=True):
    """A citizen report that a public benefit result needs correction.

    Reports keep the server-owned session reference for abuse control and
    follow-up, but never copy the caller profile or transcript into the issue
    queue. The benefit itself and the public source remain the review context.
    """

    __tablename__ = "benefit_issue_report"
    __table_args__ = (
        Index("ix_benefit_issue_report_status_created", "status", "created_at"),
        Index("ix_benefit_issue_report_benefit_created", "benefit_id", "created_at"),
    )

    id: str = Field(primary_key=True)
    benefit_id: str = Field(foreign_key="benefit.id", index=True)
    session_id: str | None = Field(default=None, foreign_key="user_session.id", index=True)
    category: str = Field(index=True)  # source | eligibility | deadline | application | other
    description: str = ""
    locale: str = ""
    status: str = Field(default="open", index=True)  # open | acknowledged | resolved | dismissed
    safe_context: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class ContactPoint(SQLModel, table=True):
    """A destination a caller has asked us to reach them at.

    The plaintext destination exists in exactly one column, encrypted. Lookup
    and deduplication run off a keyed hash, and anything user-facing shows only
    the masked suffix — so a bug that returns this row to a browser, writes it
    to a log, or backs it up somewhere unexpected does not leak a phone number.

    Verification and consent are separate columns because they answer different
    questions. Verification asks whether the destination reaches the person who
    typed it. Consent asks whether that person agreed to be messaged. Typing an
    address establishes neither.
    """

    __tablename__ = "contact_point"
    __table_args__ = (
        # One verified destination per channel per session. The hash carries
        # the uniqueness so the constraint never touches the plaintext.
        Index(
            "ix_contact_point_session_channel_hash",
            "session_id",
            "channel",
            "destination_hash",
            unique=True,
        ),
    )

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    channel: str = Field(index=True)  # email | sms | whatsapp

    destination_ciphertext: str
    destination_hash: str = Field(index=True)
    display_suffix: str = ""

    locale: str = ""
    verification_status: str = Field(default="pending", index=True)
    verification_provider: str = ""
    # Only the hash of the challenge code is stored, and only until it is used
    # or expires. The code itself is never persisted and never logged.
    verification_code_hash: str | None = None
    verification_expires_at: datetime | None = None
    verification_attempts: int = 0
    verified_at: datetime | None = None

    consent_status: str = Field(default="unknown", index=True)
    consent_purpose: str = "reminders"
    consent_source: str = ""  # browser | whatsapp_inbound | operator
    consent_at: datetime | None = None
    opted_out_at: datetime | None = None

    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)


class ConsentEvent(SQLModel, table=True):
    """Append-only evidence of every opt-in and opt-out.

    Kept as its own table rather than as columns on ContactPoint because the
    current state is not the thing under scrutiny — the question a regulator or
    a complaint asks is *when did this person agree, to what, and through what
    surface*, which only a history can answer. Rows are never updated.
    """

    __tablename__ = "consent_event"
    __table_args__ = (
        Index("ix_consent_event_contact_created", "contact_point_id", "created_at"),
    )

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    contact_point_id: str | None = Field(
        default=None, foreign_key="contact_point.id", index=True
    )
    channel: str = Field(index=True)
    purpose: str = Field(default="reminders", index=True)
    status: str = Field(index=True)  # opted_in | opted_out
    source: str = ""  # browser | sms_stop | whatsapp_inbound | operator | bounce
    # The exact wording the caller agreed to, so a later change to the consent
    # copy does not rewrite what past callers were shown.
    consent_text_version: str = ""
    actor: str = "caller"
    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class NotificationTemplate(SQLModel, table=True):
    """Mapping from an application template key to an approved provider template.

    The reminder row stores a key such as ``benefit_reminder``; this table
    resolves it per channel and locale. Keeping the indirection means a bad
    Kannada translation or a rejected DLT template is rolled back by flipping a
    row, without editing code or touching the reminders already scheduled.
    """

    __tablename__ = "notification_template"
    __table_args__ = (
        Index(
            "ix_notification_template_key_channel_locale",
            "template_key",
            "channel",
            "locale",
            unique=True,
        ),
    )

    id: str = Field(primary_key=True)
    template_key: str = Field(index=True)
    channel: str = Field(index=True)
    locale: str = Field(index=True)

    provider: str = "infobip"
    provider_template_name: str = ""
    provider_template_version: str = ""
    # DLT registration identifiers, required before any Indian SMS is legal to
    # send. Recorded here so the admin console can show which rows are ready.
    dlt_template_id: str = ""
    dlt_principal_entity_id: str = ""

    subject: str = ""
    body: str = ""
    approval_status: str = Field(default="draft", index=True)
    content_revision: int = 1
    active: bool = Field(default=False, index=True)

    updated_by: str = "system"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class NotificationDelivery(SQLModel, table=True):
    """One attempt to deliver one notification through one channel.

    Deliberately holds no message body. A template key plus safe parameters is
    enough to explain what was sent and to reproduce it, while a stored body
    would put a caller's benefit details into a table the admin console reads.
    """

    __tablename__ = "notification_delivery"
    __table_args__ = (
        # The webhook's only lookup: find the row a provider callback refers to.
        Index("ix_notification_delivery_channel_external", "channel", "external_message_id"),
        Index("ix_notification_delivery_status_next", "status", "next_attempt_at"),
    )

    id: str = Field(primary_key=True)
    reminder_id: str | None = Field(default=None, foreign_key="reminder.id", index=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    contact_point_id: str | None = Field(
        default=None, foreign_key="contact_point.id", index=True
    )

    channel: str = Field(index=True)
    provider: str = Field(default="infobip", index=True)
    template_key: str = Field(default="", index=True)
    locale: str = ""

    internal_message_id: str = Field(index=True, unique=True)
    external_message_id: str | None = Field(default=None, index=True)
    external_bulk_id: str | None = None

    status: str = Field(default="queued", index=True)
    provider_status_code: str = ""
    provider_status_group: str = ""
    provider_error_code: str = ""
    provider_error_class: str = ""

    attempt_count: int = 0
    next_attempt_at: datetime | None = Field(default=None, index=True)
    # Stable across retries of the same logical send, so a duplicate worker
    # claim or a retried 5xx cannot bill the caller's phone twice.
    idempotency_key: str = Field(index=True, unique=True)

    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    seen_at: datetime | None = None
    failed_at: datetime | None = None

    # Integer minor units with an explicit currency: messaging is billed in
    # local currency, and float rupees accumulate error across a queue drain.
    cost_minor_units: int | None = None
    cost_currency: str = ""

    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)


class Reminder(SQLModel, table=True):
    """A bounded reminder for a saved benefit.

    ``in_app`` remains the default and always works. External channels are
    accepted only when a verified contact point and live consent exist, which
    is enforced at the API rather than here — a column permitting a value is
    not the same as the product being allowed to use it.
    """

    __tablename__ = "reminder"
    __table_args__ = (
        Index("ix_reminder_session_status_due", "session_id", "status", "due_at"),
    )

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="user_session.id", index=True)
    benefit_id: str = Field(foreign_key="benefit.id", index=True)
    note: str = ""
    due_at: datetime = Field(index=True)
    timezone: str = "Asia/Kolkata"
    channel: str = "in_app"
    status: str = Field(default="scheduled", index=True)  # scheduled | delivered | cancelled
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    delivered_at: datetime | None = None

    # Set only for external channels; in_app reminders leave these null and
    # behave exactly as they did before notification delivery existed.
    contact_point_id: str | None = Field(
        default=None, foreign_key="contact_point.id", index=True
    )
    template_key: str | None = None
    # The consent record in force when the reminder was created. Kept so a
    # later opt-out is visibly a change rather than a rewrite of history.
    consent_snapshot_id: str | None = Field(
        default=None, foreign_key="consent_event.id"
    )
    next_attempt_at: datetime | None = Field(default=None, index=True)
    last_delivery_id: str | None = None


class CallSession(SQLModel, table=True):
    """Lifecycle of one inbound phone call.

    Holds no audio and no recording. A call to this service is someone saying
    their income, their caste category, and whether they have a disability out
    loud; keeping the audio would collect precisely what the rest of the system
    is built to avoid holding. What is kept is enough to bill, debug, and
    enforce limits: who called as a hash, how long it lasted, and how it ended.
    """

    __tablename__ = "call_session"
    __table_args__ = (
        Index("ix_call_session_provider_call", "provider", "provider_call_id", unique=True),
    )

    id: str = Field(primary_key=True)
    provider: str = Field(default="infobip", index=True)
    provider_call_id: str = Field(index=True)
    # The caller's number, hashed. A phone number is not stored, and the hash
    # authorizes nothing — it only lets a repeat caller resume a conversation.
    hashed_caller_identity: str = Field(index=True)
    session_id: str | None = Field(default=None, foreign_key="user_session.id", index=True)

    language_code: str = ""
    state_code: str = ""
    status: str = Field(default="ringing", index=True)

    turn_count: int = 0
    started_at: datetime = Field(default_factory=_utcnow, index=True)
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None

    provider_error_code: str = ""
    end_reason: str = ""
    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())


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


class DepartmentDirectoryEntry(SQLModel, table=True):
    """A source-attested department/help-centre routing record.

    Rows are imported as pending and become usable only after a workforce
    reviewer approves the source. Pincode and district are intentionally
    separate match keys: a pincode is a useful postal hint, not a promise that
    one office serves every address in that postal area.
    """

    __tablename__ = "department_directory_entry"
    __table_args__ = (
        Index(
            "ix_department_directory_state_service_status",
            "state_code",
            "service_domain",
            "approval_status",
            "is_active",
        ),
        Index(
            "ix_department_directory_district_service_status",
            "state_code",
            "district_name",
            "service_domain",
            "approval_status",
            "is_active",
        ),
        Index(
            "ix_department_directory_pincode_service_status",
            "pincode",
            "service_domain",
            "approval_status",
            "is_active",
        ),
        Index(
            "ix_department_directory_prefix_service_status",
            "pincode_prefix",
            "service_domain",
            "approval_status",
            "is_active",
        ),
    )

    id: str = Field(primary_key=True)
    # Stable import key makes rerunning an official directory export
    # idempotent without treating an edited source record as a new office.
    entry_key: str = Field(index=True, unique=True)
    state_code: str = Field(foreign_key="state.code", index=True)
    district_code: str = ""
    district_name: str = Field(index=True)
    service_domain: str = Field(default="citizen_support", index=True)
    pincode: str = Field(default="", index=True)
    pincode_prefix: str = Field(default="", index=True)

    department_code: str = ""
    department_name: str
    help_centre_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    website_url: str = ""

    source_name: str
    source_url: str
    source_record_id: str = ""
    source_last_verified: datetime | None = None
    valid_until: date | None = None
    working_hours: str = ""
    supported_languages: list[str] = Field(default_factory=list, sa_column=json_list())
    # Describes the evidence behind the routing key so an operator can tell
    # whether a row is an exact office/pincode record or a broader district
    # directory hint.
    coverage_basis: str = ""
    approval_status: str = Field(default="pending", index=True)  # pending | approved | rejected
    is_active: bool = Field(default=False, index=True)
    priority: int = 100
    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())
    content_revision: int = 0
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)


class DepartmentDirectoryVersion(SQLModel, table=True):
    """Immutable governance snapshot for a department directory row.

    A rollback appends a new version; it never deletes an earlier contact or
    silently changes the audit trail. Snapshots contain only directory and
    publication fields, never caller or transcript data.
    """

    __tablename__ = "department_directory_version"
    __table_args__ = (
        Index(
            "ix_department_directory_version_entry_version",
            "entry_id",
            "version",
            unique=True,
        ),
        Index(
            "ix_department_directory_version_entry_created",
            "entry_id",
            "created_at",
        ),
    )

    id: str = Field(primary_key=True)
    entry_id: str = Field(foreign_key="department_directory_entry.id", index=True)
    version: int = Field(index=True)
    action: str = Field(index=True)  # baseline | import | edit | approve | deactivate | rollback
    actor_id: str = Field(index=True)
    actor_role: str = ""
    reason: str = ""
    snapshot: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)


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
    assigned_to: str | None = Field(default=None, index=True)
    claimed_at: datetime | None = None
    sla_due_at: datetime | None = Field(default=None, index=True)
    # This is a routing target, not a claim that an official department
    # directory has been integrated. `routing_source` makes that distinction
    # visible to operators until an authoritative directory is configured.
    department: str = "National welfare and citizen-support desk"
    routing_location: str = ""
    routing_source: str = "state_domain_fallback"
    routing_directory_entry_id: str | None = Field(default=None, index=True)
    routing_source_url: str = ""
    routing_verified_at: datetime | None = None
    operator_notes: list[dict] = Field(default_factory=list, sa_column=json_list())
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_code: str | None = None
    resolution_note: str = ""


class DataImportRun(SQLModel, table=True):
    """Immutable-ish manifest for one structured data import attempt.

    The row is a compact audit record, not a replacement for the source files
    or human review notes. It lets operations answer which model, prompt, and
    input batch produced the currently loaded rows.
    """

    __tablename__ = "data_import_run"

    id: str = Field(primary_key=True)
    source_name: str = Field(index=True)
    state_code: str | None = Field(default=None, foreign_key="state.code", index=True)
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    model_name: str = ""
    prompt_version: str = ""
    input_count: int = 0
    accepted_count: int = 0
    failed_count: int = 0
    review_sample_size: int = 0
    manifest_json: dict = Field(default_factory=dict, sa_column=json_dict())


class EvaluationRun(SQLModel, table=True):
    """Immutable summary of a deterministic or provider-backed eval run."""

    __tablename__ = "evaluation_run"

    id: str = Field(primary_key=True)
    suite_name: str = Field(index=True)
    suite_version: str = ""
    passed: bool = False
    case_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    language_counts: dict = Field(default_factory=dict, sa_column=json_dict())
    report_json: dict = Field(default_factory=dict, sa_column=json_dict())
    started_at: datetime = Field(default_factory=_utcnow, index=True)
    completed_at: datetime | None = None


class DeploymentRevision(SQLModel, table=True):
    """Safe release metadata captured once per distinct deployment build."""

    __tablename__ = "deployment_revision"

    id: str = Field(primary_key=True)
    release_key: str = Field(index=True, unique=True)
    environment: str = Field(index=True)
    app_version: str = ""
    git_commit_sha: str = "unknown"
    image_digest: str = "unknown"
    migration_revision: str | None = None
    data_revision: str = ""
    prompt_version: str = ""
    model_versions: dict = Field(default_factory=dict, sa_column=json_dict())
    active_flags: dict = Field(default_factory=dict, sa_column=json_dict())
    configuration: dict = Field(default_factory=dict, sa_column=json_dict())
    deployed_at: datetime = Field(default_factory=_utcnow, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class TelemetryEvent(SQLModel, table=True):
    """Bounded, redacted operational event used by the admin console.

    This intentionally stores request shape and safe dimensions, never request
    bodies, audio, transcripts, or profile values. Raw detail belongs in a
    separately governed trace system, not in the dashboard's metric store.
    """

    __tablename__ = "telemetry_event"

    id: str = Field(primary_key=True)
    event_type: str = Field(index=True)  # http | turn | provider | system
    request_id: str | None = Field(default=None, index=True)
    trace_id: str | None = Field(default=None, index=True)
    trace_url: str | None = None
    route: str = Field(default="", index=True)
    method: str = ""
    status_code: int | None = Field(default=None, index=True)
    duration_ms: float | None = None
    surface: str = ""  # text | voice | admin | system
    language_code: str | None = Field(default=None, index=True)
    state_code: str | None = Field(default=None, index=True)
    provider: str | None = Field(default=None, index=True)
    outcome: str = ""  # success | error | no_match | escalated | fallback
    error_code: str | None = None
    safe_metadata: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class AuditEvent(SQLModel, table=True):
    """Append-only record of workforce access and state changes."""

    __tablename__ = "audit_event"

    id: str = Field(primary_key=True)
    actor_id: str = Field(index=True)
    actor_role: str = Field(index=True)
    action: str = Field(index=True)
    target_type: str = Field(index=True)
    target_id: str = ""
    reason: str = ""
    safe_before: dict = Field(default_factory=dict, sa_column=json_dict())
    safe_after: dict = Field(default_factory=dict, sa_column=json_dict())
    request_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class ProviderPolicy(SQLModel, table=True):
    """Current provider routing/circuit policy for one bounded scope."""

    __tablename__ = "provider_policy"
    __table_args__ = (
        Index("ix_provider_policy_provider_scope", "provider", "scope", unique=True),
    )

    id: str = Field(primary_key=True)
    provider: str = Field(index=True)  # tts | stt | rag | reasoning
    scope: str = Field(default="*", index=True)  # locale, state, or *
    enabled: bool = True
    primary_provider: str = ""
    fallback_provider: str | None = None
    circuit_state: str = "closed"  # closed | open | half_open
    daily_budget_usd: float | None = None
    monthly_budget_usd: float | None = None
    override_expires_at: datetime | None = None
    revision: int = 0
    config: dict = Field(default_factory=dict, sa_column=json_dict())
    updated_by: str = "system"
    updated_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)


class ProviderPolicyRevision(SQLModel, table=True):
    """Append-only before/after snapshots supporting audited rollback."""

    __tablename__ = "provider_policy_revision"

    id: str = Field(primary_key=True)
    policy_id: str = Field(index=True, foreign_key="provider_policy.id")
    revision: int = Field(index=True)
    action: str = Field(index=True)  # update | rollback | expire
    actor_id: str = Field(index=True)
    actor_role: str = ""
    reason: str = ""
    before: dict = Field(default_factory=dict, sa_column=json_dict())
    after: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class FeatureFlag(SQLModel, table=True):
    """A bounded rollout switch controlled by the workforce console."""

    __tablename__ = "feature_flag"

    id: str = Field(primary_key=True)
    key: str = Field(index=True, unique=True)
    description: str = ""
    enabled: bool = False
    rollout_percentage: int = 0
    target_languages: list[str] = Field(default_factory=list, sa_column=json_list())
    target_states: list[str] = Field(default_factory=list, sa_column=json_list())
    config: dict = Field(default_factory=dict, sa_column=json_dict())
    revision: int = 0
    updated_by: str = "system"
    updated_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)


class FeatureFlagRevision(SQLModel, table=True):
    """Append-only before/after snapshots supporting flag rollback."""

    __tablename__ = "feature_flag_revision"

    id: str = Field(primary_key=True)
    flag_id: str = Field(index=True, foreign_key="feature_flag.id")
    revision: int = Field(index=True)
    action: str = Field(index=True)  # update | rollback
    actor_id: str = Field(index=True)
    actor_role: str = ""
    reason: str = ""
    before: dict = Field(default_factory=dict, sa_column=json_dict())
    after: dict = Field(default_factory=dict, sa_column=json_dict())
    created_at: datetime = Field(default_factory=_utcnow, index=True)
