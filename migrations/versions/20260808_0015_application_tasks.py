"""Add private document and application task tracking."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0015"
down_revision = "20260808_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_task",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_task_session_id", "application_task", ["session_id"])
    op.create_index("ix_application_task_benefit_id", "application_task", ["benefit_id"])
    op.create_index("ix_application_task_kind", "application_task", ["kind"])
    op.create_index("ix_application_task_status", "application_task", ["status"])
    op.create_index("ix_application_task_due_at", "application_task", ["due_at"])
    op.create_index("ix_application_task_created_at", "application_task", ["created_at"])
    op.create_index(
        "ix_application_task_session_benefit_status",
        "application_task",
        ["session_id", "benefit_id", "status"],
    )
    op.create_index(
        "ix_application_task_session_benefit_title",
        "application_task",
        ["session_id", "benefit_id", "kind", "title"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_application_task_session_benefit_title", table_name="application_task")
    op.drop_index("ix_application_task_session_benefit_status", table_name="application_task")
    for name in ("created_at", "due_at", "status", "kind", "benefit_id", "session_id"):
        op.drop_index(f"ix_application_task_{name}", table_name="application_task")
    op.drop_table("application_task")

