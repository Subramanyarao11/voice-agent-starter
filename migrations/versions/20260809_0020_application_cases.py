"""Add citizen application cases and append-only status evidence."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0020"
down_revision = "20260809_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_case",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("benefit_revision", sa.Integer(), nullable=False),
        sa.Column("benefit_snapshot", sa.JSON(), nullable=False),
        sa.Column("application_channel", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("status_provenance", sa.String(), nullable=False),
        sa.Column("status_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_source_url", sa.String(), nullable=False),
        sa.Column("readiness_state", sa.String(), nullable=False),
        sa.Column("readiness_blockers", sa.JSON(), nullable=False),
        sa.Column("external_reference_ciphertext", sa.String(), nullable=True),
        sa.Column("external_reference_hash", sa.String(), nullable=True),
        sa.Column("external_reference_masked", sa.String(), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["user_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_case_session_id", ["session_id"]),
        ("ix_application_case_benefit_id", ["benefit_id"]),
        ("ix_application_case_status", ["status"]),
        ("ix_application_case_status_recorded_at", ["status_recorded_at"]),
        ("ix_application_case_external_reference_hash", ["external_reference_hash"]),
        ("ix_application_case_created_at", ["created_at"]),
        ("ix_application_case_updated_at", ["updated_at"]),
        (
            "ix_application_case_session_status_updated",
            ["session_id", "status", "updated_at"],
        ),
        (
            "ix_application_case_session_benefit_status",
            ["session_id", "benefit_id", "status"],
        ),
    ):
        op.create_index(name, "application_case", columns)

    op.create_table(
        "application_status_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_case_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provenance", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("external_reference_masked", sa.String(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["application_case_id"], ["application_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_status_event_application_case_id", ["application_case_id"]),
        ("ix_application_status_event_status", ["status"]),
        ("ix_application_status_event_provenance", ["provenance"]),
        ("ix_application_status_event_occurred_at", ["occurred_at"]),
        ("ix_application_status_event_recorded_at", ["recorded_at"]),
        (
            "ix_application_status_event_case_occurred",
            ["application_case_id", "occurred_at"],
        ),
        (
            "ix_application_status_event_case_recorded",
            ["application_case_id", "recorded_at"],
        ),
    ):
        op.create_index(name, "application_status_event", columns)

    # Existing personal checklist rows remain valid. New cases attach their
    # materialized rows here; nullable keeps the migration backward-safe.
    with op.batch_alter_table("application_task") as batch:
        batch.add_column(sa.Column("application_case_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_application_task_application_case_id",
            "application_case",
            ["application_case_id"],
            ["id"],
        )
        batch.create_index("ix_application_task_application_case_id", ["application_case_id"])


def downgrade() -> None:
    with op.batch_alter_table("application_task") as batch:
        batch.drop_index("ix_application_task_application_case_id")
        batch.drop_constraint("fk_application_task_application_case_id", type_="foreignkey")
        batch.drop_column("application_case_id")

    for name in (
        "ix_application_status_event_case_recorded",
        "ix_application_status_event_case_occurred",
        "ix_application_status_event_recorded_at",
        "ix_application_status_event_occurred_at",
        "ix_application_status_event_provenance",
        "ix_application_status_event_status",
        "ix_application_status_event_application_case_id",
    ):
        op.drop_index(name, table_name="application_status_event")
    op.drop_table("application_status_event")

    for name in (
        "ix_application_case_session_benefit_status",
        "ix_application_case_session_status_updated",
        "ix_application_case_updated_at",
        "ix_application_case_created_at",
        "ix_application_case_external_reference_hash",
        "ix_application_case_status_recorded_at",
        "ix_application_case_status",
        "ix_application_case_benefit_id",
        "ix_application_case_session_id",
    ):
        op.drop_index(name, table_name="application_case")
    op.drop_table("application_case")
