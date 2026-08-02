"""Add private saved-benefit shortlists and in-app reminders."""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0007"
down_revision = "20260802_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_benefit",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_benefit_session_id", "saved_benefit", ["session_id"])
    op.create_index("ix_saved_benefit_benefit_id", "saved_benefit", ["benefit_id"])
    op.create_index("ix_saved_benefit_created_at", "saved_benefit", ["created_at"])
    op.create_index(
        "ix_saved_benefit_session_benefit",
        "saved_benefit",
        ["session_id", "benefit_id"],
        unique=True,
    )

    op.create_table(
        "reminder",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminder_session_id", "reminder", ["session_id"])
    op.create_index("ix_reminder_benefit_id", "reminder", ["benefit_id"])
    op.create_index("ix_reminder_due_at", "reminder", ["due_at"])
    op.create_index("ix_reminder_status", "reminder", ["status"])
    op.create_index("ix_reminder_created_at", "reminder", ["created_at"])
    op.create_index(
        "ix_reminder_session_status_due",
        "reminder",
        ["session_id", "status", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reminder_session_status_due", table_name="reminder")
    op.drop_index("ix_reminder_created_at", table_name="reminder")
    op.drop_index("ix_reminder_status", table_name="reminder")
    op.drop_index("ix_reminder_due_at", table_name="reminder")
    op.drop_index("ix_reminder_benefit_id", table_name="reminder")
    op.drop_index("ix_reminder_session_id", table_name="reminder")
    op.drop_table("reminder")
    op.drop_index("ix_saved_benefit_session_benefit", table_name="saved_benefit")
    op.drop_index("ix_saved_benefit_created_at", table_name="saved_benefit")
    op.drop_index("ix_saved_benefit_benefit_id", table_name="saved_benefit")
    op.drop_index("ix_saved_benefit_session_id", table_name="saved_benefit")
    op.drop_table("saved_benefit")
