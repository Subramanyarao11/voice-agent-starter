"""Add citizen reports for incorrect benefit information."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0011"
down_revision = "20260808_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benefit_issue_report",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("safe_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benefit_issue_report_benefit_id", "benefit_issue_report", ["benefit_id"])
    op.create_index("ix_benefit_issue_report_session_id", "benefit_issue_report", ["session_id"])
    op.create_index("ix_benefit_issue_report_category", "benefit_issue_report", ["category"])
    op.create_index("ix_benefit_issue_report_status", "benefit_issue_report", ["status"])
    op.create_index("ix_benefit_issue_report_created_at", "benefit_issue_report", ["created_at"])
    op.create_index(
        "ix_benefit_issue_report_status_created",
        "benefit_issue_report",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_benefit_issue_report_benefit_created",
        "benefit_issue_report",
        ["benefit_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_benefit_issue_report_benefit_created", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_status_created", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_created_at", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_status", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_category", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_session_id", table_name="benefit_issue_report")
    op.drop_index("ix_benefit_issue_report_benefit_id", table_name="benefit_issue_report")
    op.drop_table("benefit_issue_report")
