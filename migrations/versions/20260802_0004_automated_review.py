"""Store machine-review findings separately from human verification."""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0004"
down_revision = "20260802_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benefit",
        sa.Column(
            "automated_review",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("benefit", "automated_review")
