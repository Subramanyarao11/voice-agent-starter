"""Add operator ownership, routing, SLA, notes, and resolution metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0012"
down_revision = "20260808_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escalation_ticket", sa.Column("assigned_to", sa.String(), nullable=True))
    op.add_column(
        "escalation_ticket",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column(
            "department",
            sa.String(),
            nullable=False,
            server_default="National welfare and citizen-support desk",
        ),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column("routing_location", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column("routing_source", sa.String(), nullable=False, server_default="legacy_unrouted"),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column("operator_notes", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "escalation_ticket",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("escalation_ticket", sa.Column("resolved_by", sa.String(), nullable=True))
    op.add_column("escalation_ticket", sa.Column("resolution_code", sa.String(), nullable=True))
    op.add_column(
        "escalation_ticket",
        sa.Column("resolution_note", sa.String(), nullable=False, server_default=""),
    )
    op.create_index("ix_escalation_ticket_assigned_to", "escalation_ticket", ["assigned_to"])
    op.create_index("ix_escalation_ticket_sla_due_at", "escalation_ticket", ["sla_due_at"])

    # Existing tickets predate the SLA fields. They remain visible and receive
    # a conservative deadline from their creation time instead of silently
    # disappearing from the operator queue.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE escalation_ticket "
            "SET updated_at = created_at, "
            "sla_due_at = created_at + interval '24 hours' "
            "WHERE updated_at IS NULL OR sla_due_at IS NULL"
        )
    else:
        op.execute(
            "UPDATE escalation_ticket SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
        # SQLite's date arithmetic is only needed for legacy local rows. The
        # API treats a null deadline as an unclocked legacy ticket.

    # PostgreSQL can remove the temporary defaults directly. SQLite's ALTER
    # TABLE implementation cannot drop a default without reconstructing the
    # table, and these defaults are harmless for the legacy compatibility
    # columns. The application owns future writes, so leave them in place on
    # local SQLite databases rather than making a clean install fail here.
    if bind.dialect.name != "sqlite":
        for column in (
            "department",
            "routing_location",
            "routing_source",
            "operator_notes",
            "resolution_note",
        ):
            op.alter_column("escalation_ticket", column, server_default=None)


def downgrade() -> None:
    op.drop_index("ix_escalation_ticket_sla_due_at", table_name="escalation_ticket")
    op.drop_index("ix_escalation_ticket_assigned_to", table_name="escalation_ticket")
    for column in (
        "resolution_note",
        "resolution_code",
        "resolved_by",
        "updated_at",
        "operator_notes",
        "routing_source",
        "routing_location",
        "department",
        "sla_due_at",
        "claimed_at",
        "assigned_to",
    ):
        op.drop_column("escalation_ticket", column)
