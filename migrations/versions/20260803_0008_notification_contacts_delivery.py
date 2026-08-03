"""Add contact points, consent history, notification templates, and deliveries.

Additive only. Existing in-app reminders keep working unchanged: the new
Reminder columns are all nullable, and a row with a null contact point is
exactly the in-app reminder the product already ships.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260803_0008"
down_revision = "20260802_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_point",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        # The only place a destination exists, and only as ciphertext.
        sa.Column("destination_ciphertext", sa.String(), nullable=False),
        sa.Column("destination_hash", sa.String(), nullable=False),
        sa.Column("display_suffix", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("verification_provider", sa.String(), nullable=False),
        sa.Column("verification_code_hash", sa.String(), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_attempts", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_status", sa.String(), nullable=False),
        sa.Column("consent_purpose", sa.String(), nullable=False),
        sa.Column("consent_source", sa.String(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_point_session_id", "contact_point", ["session_id"])
    op.create_index("ix_contact_point_channel", "contact_point", ["channel"])
    op.create_index("ix_contact_point_destination_hash", "contact_point", ["destination_hash"])
    op.create_index(
        "ix_contact_point_verification_status", "contact_point", ["verification_status"]
    )
    op.create_index("ix_contact_point_consent_status", "contact_point", ["consent_status"])
    op.create_index("ix_contact_point_created_at", "contact_point", ["created_at"])
    op.create_index(
        "ix_contact_point_session_channel_hash",
        "contact_point",
        ["session_id", "channel", "destination_hash"],
        unique=True,
    )

    op.create_table(
        "consent_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("contact_point_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("consent_text_version", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_point_id"], ["contact_point.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_event_session_id", "consent_event", ["session_id"])
    op.create_index("ix_consent_event_contact_point_id", "consent_event", ["contact_point_id"])
    op.create_index("ix_consent_event_channel", "consent_event", ["channel"])
    op.create_index("ix_consent_event_purpose", "consent_event", ["purpose"])
    op.create_index("ix_consent_event_status", "consent_event", ["status"])
    op.create_index("ix_consent_event_created_at", "consent_event", ["created_at"])
    op.create_index(
        "ix_consent_event_contact_created",
        "consent_event",
        ["contact_point_id", "created_at"],
    )

    op.create_table(
        "notification_template",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_template_name", sa.String(), nullable=False),
        sa.Column("provider_template_version", sa.String(), nullable=False),
        sa.Column("dlt_template_id", sa.String(), nullable=False),
        sa.Column("dlt_principal_entity_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("approval_status", sa.String(), nullable=False),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_template_key", "notification_template", ["template_key"])
    op.create_index("ix_notification_template_channel", "notification_template", ["channel"])
    op.create_index("ix_notification_template_locale", "notification_template", ["locale"])
    op.create_index(
        "ix_notification_template_approval_status", "notification_template", ["approval_status"]
    )
    op.create_index("ix_notification_template_active", "notification_template", ["active"])
    op.create_index(
        "ix_notification_template_key_channel_locale",
        "notification_template",
        ["template_key", "channel", "locale"],
        unique=True,
    )

    op.create_table(
        "notification_delivery",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reminder_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("contact_point_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("internal_message_id", sa.String(), nullable=False),
        sa.Column("external_message_id", sa.String(), nullable=True),
        sa.Column("external_bulk_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider_status_code", sa.String(), nullable=False),
        sa.Column("provider_status_group", sa.String(), nullable=False),
        sa.Column("provider_error_code", sa.String(), nullable=False),
        sa.Column("provider_error_class", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_minor_units", sa.Integer(), nullable=True),
        sa.Column("cost_currency", sa.String(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_point_id"], ["contact_point.id"]),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminder.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_delivery_reminder_id", "notification_delivery", ["reminder_id"]
    )
    op.create_index(
        "ix_notification_delivery_session_id", "notification_delivery", ["session_id"]
    )
    op.create_index(
        "ix_notification_delivery_contact_point_id",
        "notification_delivery",
        ["contact_point_id"],
    )
    op.create_index("ix_notification_delivery_channel", "notification_delivery", ["channel"])
    op.create_index("ix_notification_delivery_provider", "notification_delivery", ["provider"])
    op.create_index(
        "ix_notification_delivery_template_key", "notification_delivery", ["template_key"]
    )
    op.create_index(
        "ix_notification_delivery_internal_message_id",
        "notification_delivery",
        ["internal_message_id"],
        unique=True,
    )
    op.create_index(
        "ix_notification_delivery_external_message_id",
        "notification_delivery",
        ["external_message_id"],
    )
    op.create_index("ix_notification_delivery_status", "notification_delivery", ["status"])
    op.create_index(
        "ix_notification_delivery_next_attempt_at",
        "notification_delivery",
        ["next_attempt_at"],
    )
    op.create_index(
        "ix_notification_delivery_idempotency_key",
        "notification_delivery",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_notification_delivery_created_at", "notification_delivery", ["created_at"]
    )
    op.create_index(
        "ix_notification_delivery_channel_external",
        "notification_delivery",
        ["channel", "external_message_id"],
    )
    op.create_index(
        "ix_notification_delivery_status_next",
        "notification_delivery",
        ["status", "next_attempt_at"],
    )

    # Reminder gains external-channel columns. All nullable, so every existing
    # in_app row remains valid without a data migration.
    with op.batch_alter_table("reminder") as batch:
        batch.add_column(sa.Column("contact_point_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("template_key", sa.String(), nullable=True))
        batch.add_column(sa.Column("consent_snapshot_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("last_delivery_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_reminder_contact_point_id", "contact_point", ["contact_point_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_reminder_consent_snapshot_id", "consent_event", ["consent_snapshot_id"], ["id"]
        )
    op.create_index("ix_reminder_contact_point_id", "reminder", ["contact_point_id"])
    op.create_index("ix_reminder_next_attempt_at", "reminder", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_reminder_next_attempt_at", table_name="reminder")
    op.drop_index("ix_reminder_contact_point_id", table_name="reminder")
    with op.batch_alter_table("reminder") as batch:
        batch.drop_constraint("fk_reminder_consent_snapshot_id", type_="foreignkey")
        batch.drop_constraint("fk_reminder_contact_point_id", type_="foreignkey")
        batch.drop_column("last_delivery_id")
        batch.drop_column("next_attempt_at")
        batch.drop_column("consent_snapshot_id")
        batch.drop_column("template_key")
        batch.drop_column("contact_point_id")

    op.drop_table("notification_delivery")
    op.drop_table("notification_template")
    op.drop_table("consent_event")
    op.drop_table("contact_point")
