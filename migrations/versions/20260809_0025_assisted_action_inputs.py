"""Store only encrypted inputs for confirmed downstream Saathi actions."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0025"
down_revision = "20260809_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistance_action",
        sa.Column("requested_reference_ciphertext", sa.String(), nullable=True),
    )
    op.add_column(
        "assistance_action",
        sa.Column("requested_reference_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "assistance_action",
        sa.Column("requested_reference_masked", sa.String(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_assistance_action_requested_reference_hash",
        "assistance_action",
        ["requested_reference_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistance_action_requested_reference_hash",
        table_name="assistance_action",
    )
    op.drop_column("assistance_action", "requested_reference_masked")
    op.drop_column("assistance_action", "requested_reference_hash")
    op.drop_column("assistance_action", "requested_reference_ciphertext")
