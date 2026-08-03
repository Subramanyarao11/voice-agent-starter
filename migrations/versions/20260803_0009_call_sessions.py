"""Add inbound call lifecycle records.

Deliberately no recording or transcript column. A call to this service is
someone stating their income and category out loud, and a table that could hold
that audio would eventually hold it.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260803_0009"
down_revision = "20260803_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_call_id", sa.String(), nullable=False),
        sa.Column("hashed_caller_identity", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("language_code", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("provider_error_code", sa.String(), nullable=False),
        sa.Column("end_reason", sa.String(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_session_provider", "call_session", ["provider"])
    op.create_index("ix_call_session_provider_call_id", "call_session", ["provider_call_id"])
    op.create_index(
        "ix_call_session_hashed_caller_identity", "call_session", ["hashed_caller_identity"]
    )
    op.create_index("ix_call_session_session_id", "call_session", ["session_id"])
    op.create_index("ix_call_session_status", "call_session", ["status"])
    op.create_index("ix_call_session_started_at", "call_session", ["started_at"])
    op.create_index(
        "ix_call_session_provider_call",
        "call_session",
        ["provider", "provider_call_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("call_session")
