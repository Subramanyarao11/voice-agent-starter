"""Add bounded Assisted Saathi sessions, consent, and action audit tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0023"
down_revision = "20260809_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistance_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("invitation_token_hash", sa.String(), nullable=True),
        sa.Column("citizen_session_id", sa.String(), nullable=True),
        sa.Column("citizen_account_id", sa.String(), nullable=True),
        sa.Column("household_id", sa.String(), nullable=True),
        sa.Column("household_member_id", sa.String(), nullable=True),
        sa.Column("helper_actor_id", sa.String(), nullable=True),
        sa.Column("helper_org_id", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("approved_data_categories", sa.JSON(), nullable=False),
        sa.Column("allowed_action_keys", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("projection_version", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["citizen_session_id"], ["user_session.id"]),
        sa.ForeignKeyConstraint(["citizen_account_id"], ["citizen_account.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.ForeignKeyConstraint(["household_member_id"], ["household_member.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_token_hash"),
    )
    for name, columns in (
        ("ix_assistance_session_invitation_token_hash", ["invitation_token_hash"]),
        ("ix_assistance_session_citizen_session_id", ["citizen_session_id"]),
        ("ix_assistance_session_citizen_account_id", ["citizen_account_id"]),
        ("ix_assistance_session_household_id", ["household_id"]),
        ("ix_assistance_session_household_member_id", ["household_member_id"]),
        ("ix_assistance_session_helper_actor_id", ["helper_actor_id"]),
        ("ix_assistance_session_purpose", ["purpose"]),
        ("ix_assistance_session_status", ["status"]),
        ("ix_assistance_session_expires_at", ["expires_at"]),
        ("ix_assistance_session_last_activity_at", ["last_activity_at"]),
        ("ix_assistance_session_created_at", ["created_at"]),
        (
            "ix_assistance_session_account_status",
            ["citizen_account_id", "status"],
        ),
        (
            "ix_assistance_session_helper_status",
            ["helper_actor_id", "status"],
        ),
        (
            "ix_assistance_session_expiry_status",
            ["expires_at", "status"],
        ),
    ):
        op.create_index(name, "assistance_session", columns)

    op.create_table(
        "assistance_consent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("assistance_session_id", sa.String(), nullable=False),
        sa.Column("citizen_account_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("notice_version", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("confirmation_mode", sa.String(), nullable=False),
        sa.Column("approved_data_categories", sa.JSON(), nullable=False),
        sa.Column("approved_action_keys", sa.JSON(), nullable=False),
        sa.Column("citizen_subject_hash", sa.String(), nullable=False),
        sa.Column("helper_actor_id", sa.String(), nullable=False),
        sa.Column("helper_org_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistance_session_id"], ["assistance_session.id"]),
        sa.ForeignKeyConstraint(["citizen_account_id"], ["citizen_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_assistance_consent_assistance_session_id", ["assistance_session_id"]),
        ("ix_assistance_consent_citizen_account_id", ["citizen_account_id"]),
        ("ix_assistance_consent_action", ["action"]),
        ("ix_assistance_consent_created_at", ["created_at"]),
        (
            "ix_assistance_consent_session_created",
            ["assistance_session_id", "created_at"],
        ),
    ):
        op.create_index(name, "assistance_consent", columns)

    op.create_table(
        "assistance_action",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("assistance_session_id", sa.String(), nullable=False),
        sa.Column("action_key", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("helper_actor_id", sa.String(), nullable=False),
        sa.Column("confirmation_actor_hash", sa.String(), nullable=False),
        sa.Column("confirmation_mode", sa.String(), nullable=False),
        sa.Column("safe_preview", sa.JSON(), nullable=False),
        sa.Column("before_safe_hash", sa.String(), nullable=False),
        sa.Column("after_safe_hash", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistance_session_id"], ["assistance_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assistance_session_id",
            "idempotency_key",
            name="uq_assistance_action_session_idempotency",
        ),
    )
    for name, columns in (
        ("ix_assistance_action_assistance_session_id", ["assistance_session_id"]),
        ("ix_assistance_action_action_key", ["action_key"]),
        ("ix_assistance_action_stage", ["stage"]),
        ("ix_assistance_action_idempotency_key", ["idempotency_key"]),
        ("ix_assistance_action_created_at", ["created_at"]),
        (
            "ix_assistance_action_session_created",
            ["assistance_session_id", "created_at"],
        ),
        (
            "ix_assistance_action_session_idempotency",
            ["assistance_session_id", "idempotency_key"],
        ),
    ):
        op.create_index(name, "assistance_action", columns)


def downgrade() -> None:
    for name in (
        "ix_assistance_action_session_idempotency",
        "ix_assistance_action_session_created",
        "ix_assistance_action_created_at",
        "ix_assistance_action_idempotency_key",
        "ix_assistance_action_stage",
        "ix_assistance_action_action_key",
        "ix_assistance_action_assistance_session_id",
    ):
        op.drop_index(name, table_name="assistance_action")
    op.drop_table("assistance_action")

    for name in (
        "ix_assistance_consent_session_created",
        "ix_assistance_consent_created_at",
        "ix_assistance_consent_action",
        "ix_assistance_consent_citizen_account_id",
        "ix_assistance_consent_assistance_session_id",
    ):
        op.drop_index(name, table_name="assistance_consent")
    op.drop_table("assistance_consent")

    for name in (
        "ix_assistance_session_expiry_status",
        "ix_assistance_session_helper_status",
        "ix_assistance_session_account_status",
        "ix_assistance_session_created_at",
        "ix_assistance_session_last_activity_at",
        "ix_assistance_session_expires_at",
        "ix_assistance_session_status",
        "ix_assistance_session_purpose",
        "ix_assistance_session_helper_actor_id",
        "ix_assistance_session_household_member_id",
        "ix_assistance_session_household_id",
        "ix_assistance_session_citizen_account_id",
        "ix_assistance_session_citizen_session_id",
        "ix_assistance_session_invitation_token_hash",
    ):
        op.drop_index(name, table_name="assistance_session")
    op.drop_table("assistance_session")
