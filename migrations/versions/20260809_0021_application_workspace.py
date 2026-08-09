"""Add governed application fields, requirements, and outcomes."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0021"
down_revision = "20260809_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("application_case") as batch:
        batch.add_column(
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("provider_key", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True)
        )

    with op.batch_alter_table("application_task") as batch:
        batch.add_column(sa.Column("requirement_key", sa.String(), nullable=True))
        batch.create_index("ix_application_task_requirement_key", ["requirement_key"])

    op.create_table(
        "application_field_definition",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("label", sa.JSON(), nullable=False),
        sa.Column("help_text", sa.JSON(), nullable=False),
        sa.Column("data_type", sa.String(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sensitivity", sa.String(), nullable=False),
        sa.Column("source_excerpt", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("profile_slot", sa.String(), nullable=True),
        sa.Column("handoff_destinations", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_field_definition_benefit_id", ["benefit_id"]),
        ("ix_application_field_definition_field_key", ["field_key"]),
        ("ix_application_field_definition_review_status", ["review_status"]),
        (
            "ix_application_field_definition_benefit_key_revision",
            ["benefit_id", "field_key", "revision"],
        ),
        (
            "ix_application_field_definition_benefit_review",
            ["benefit_id", "review_status"],
        ),
    ):
        op.create_index(
            name,
            "application_field_definition",
            columns,
            unique=name.endswith("key_revision"),
        )

    op.create_table(
        "application_field_value",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_case_id", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("definition_revision", sa.Integer(), nullable=False),
        sa.Column("value_ciphertext", sa.String(), nullable=False),
        sa.Column("value_hash", sa.String(), nullable=False),
        sa.Column("masked_value", sa.String(), nullable=False),
        sa.Column("value_source", sa.String(), nullable=False),
        sa.Column("confirmed_by_citizen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_case_id"], ["application_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_field_value_application_case_id", ["application_case_id"]),
        ("ix_application_field_value_field_key", ["field_key"]),
        ("ix_application_field_value_value_hash", ["value_hash"]),
        (
            "ix_application_field_value_case_key",
            ["application_case_id", "field_key"],
        ),
        (
            "ix_application_field_value_case_updated",
            ["application_case_id", "updated_at"],
        ),
    ):
        op.create_index(
            name,
            "application_field_value",
            columns,
            unique=name.endswith("case_key"),
        )

    op.create_table(
        "application_requirement",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_case_id", sa.String(), nullable=False),
        sa.Column("requirement_key", sa.String(), nullable=False),
        sa.Column("requirement_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_excerpt", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_case_id"], ["application_case.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["application_task.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_requirement_application_case_id", ["application_case_id"]),
        ("ix_application_requirement_requirement_key", ["requirement_key"]),
        ("ix_application_requirement_status", ["status"]),
        (
            "ix_application_requirement_case_key",
            ["application_case_id", "requirement_key"],
        ),
        (
            "ix_application_requirement_case_status",
            ["application_case_id", "status"],
        ),
    ):
        op.create_index(
            name,
            "application_requirement",
            columns,
            unique=name.endswith("case_key"),
        )

    op.create_table(
        "application_outcome_feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_case_id", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("free_text_ciphertext", sa.String(), nullable=True),
        sa.Column("satisfaction_score", sa.Integer(), nullable=True),
        sa.Column("consent_for_evaluation", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_case_id"], ["application_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_application_outcome_feedback_application_case_id", ["application_case_id"]),
        ("ix_application_outcome_feedback_outcome", ["outcome"]),
        (
            "ix_application_outcome_feedback_case",
            ["application_case_id"],
        ),
    ):
        op.create_index(
            name,
            "application_outcome_feedback",
            columns,
            unique=name.endswith("case"),
        )


def downgrade() -> None:
    for name in (
        "ix_application_outcome_feedback_case",
        "ix_application_outcome_feedback_outcome",
        "ix_application_outcome_feedback_application_case_id",
    ):
        op.drop_index(name, table_name="application_outcome_feedback")
    op.drop_table("application_outcome_feedback")

    for name in (
        "ix_application_requirement_case_status",
        "ix_application_requirement_case_key",
        "ix_application_requirement_status",
        "ix_application_requirement_requirement_key",
        "ix_application_requirement_application_case_id",
    ):
        op.drop_index(name, table_name="application_requirement")
    op.drop_table("application_requirement")

    for name in (
        "ix_application_field_value_case_updated",
        "ix_application_field_value_case_key",
        "ix_application_field_value_value_hash",
        "ix_application_field_value_field_key",
        "ix_application_field_value_application_case_id",
    ):
        op.drop_index(name, table_name="application_field_value")
    op.drop_table("application_field_value")

    for name in (
        "ix_application_field_definition_benefit_review",
        "ix_application_field_definition_benefit_key_revision",
        "ix_application_field_definition_review_status",
        "ix_application_field_definition_field_key",
        "ix_application_field_definition_benefit_id",
    ):
        op.drop_index(name, table_name="application_field_definition")
    op.drop_table("application_field_definition")

    with op.batch_alter_table("application_task") as batch:
        batch.drop_index("ix_application_task_requirement_key")
        batch.drop_column("requirement_key")

    with op.batch_alter_table("application_case") as batch:
        batch.drop_column("retention_expires_at")
        batch.drop_column("provider_key")
        batch.drop_column("attempt_number")
