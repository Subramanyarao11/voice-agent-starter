"""Create the pre-provenance Sahaayak schema.

This baseline mirrors the schema that existed before Alembic was introduced.
Keeping provenance in the following revision lets an existing local database
be stamped at this point and upgraded without losing its demo rows.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("native_name", sa.String(), nullable=False),
        sa.Column("stt_provider", sa.String(), nullable=False),
        sa.Column("stt_locale", sa.String(), nullable=False),
        sa.Column("tts_provider", sa.String(), nullable=False),
        sa.Column("tts_locale", sa.String(), nullable=False),
        sa.Column("tts_voice_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "state",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("primary_language_code", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["primary_language_code"], ["language.code"]),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "benefit",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("eligibility_initial", sa.JSON(), nullable=False),
        sa.Column("eligibility_renewal", sa.JSON(), nullable=True),
        sa.Column("benefits_text", sa.String(), nullable=False),
        sa.Column("documents_required", sa.JSON(), nullable=False),
        sa.Column("application_process", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("last_verified_date", sa.Date(), nullable=False),
        sa.Column("localized_summary", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["state_code"], ["state.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benefit_domain", "benefit", ["domain"], unique=False)
    op.create_index("ix_benefit_state_code", "benefit", ["state_code"], unique=False)
    op.create_index(
        "ix_benefit_domain_state", "benefit", ["domain", "state_code"], unique=False
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("phone_or_session_id", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=False),
        sa.Column("language_code", sa.String(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("conversation_state", sa.JSON(), nullable=False),
        sa.Column("open_tasks", sa.JSON(), nullable=False),
        sa.Column("matched_benefit_ids", sa.JSON(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["language_code"], ["language.code"]),
        sa.ForeignKeyConstraint(["state_code"], ["state.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_or_session_id"),
    )
    op.create_index(
        "ix_user_session_phone_or_session_id",
        "user_session",
        ["phone_or_session_id"],
        unique=True,
    )
    op.create_table(
        "conversation_turn_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("slots_after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_turn_log_session_id",
        "conversation_turn_log",
        ["session_id"],
        unique=False,
    )
    op.create_table(
        "escalation_ticket",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("caller_context", sa.JSON(), nullable=False),
        sa.Column("transcript_excerpt", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_escalation_ticket_session_id", "escalation_ticket", ["session_id"], unique=False
    )
    op.create_index(
        "ix_escalation_ticket_status", "escalation_ticket", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_escalation_ticket_status", table_name="escalation_ticket")
    op.drop_index("ix_escalation_ticket_session_id", table_name="escalation_ticket")
    op.drop_table("escalation_ticket")
    op.drop_index("ix_conversation_turn_log_session_id", table_name="conversation_turn_log")
    op.drop_table("conversation_turn_log")
    op.drop_index("ix_user_session_phone_or_session_id", table_name="user_session")
    op.drop_table("user_session")
    op.drop_index("ix_benefit_domain_state", table_name="benefit")
    op.drop_index("ix_benefit_state_code", table_name="benefit")
    op.drop_index("ix_benefit_domain", table_name="benefit")
    op.drop_table("benefit")
    op.drop_table("state")
    op.drop_table("language")
