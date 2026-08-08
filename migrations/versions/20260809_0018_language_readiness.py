"""Add language release evidence gates."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0018"
down_revision = "20260809_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language_readiness_review",
        sa.Column("language_code", sa.String(), nullable=False),
        sa.Column("native_speaker_status", sa.String(), nullable=False),
        sa.Column("interface_status", sa.String(), nullable=False),
        sa.Column("prompt_status", sa.String(), nullable=False),
        sa.Column("content_status", sa.String(), nullable=False),
        sa.Column("understanding_status", sa.String(), nullable=False),
        sa.Column("voice_status", sa.String(), nullable=False),
        sa.Column("accessibility_status", sa.String(), nullable=False),
        sa.Column("evidence_url", sa.String(), nullable=False),
        sa.Column("review_notes", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["language_code"], ["language.code"]),
        sa.PrimaryKeyConstraint("language_code"),
    )


def downgrade() -> None:
    op.drop_table("language_readiness_review")
