"""Add evaluation run history and audited feature-flag rollouts."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0013"
down_revision = "20260808_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_run",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("suite_name", sa.String(), nullable=False),
        sa.Column("suite_version", sa.String(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("language_counts", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_run_suite_name", "evaluation_run", ["suite_name"])
    op.create_index("ix_evaluation_run_started_at", "evaluation_run", ["started_at"])

    op.create_table(
        "feature_flag",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), nullable=False),
        sa.Column("target_languages", sa.JSON(), nullable=False),
        sa.Column("target_states", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_feature_flag_key", "feature_flag", ["key"])

    op.create_table(
        "feature_flag_revision",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("flag_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["flag_id"], ["feature_flag.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("flag_id", "flag_id"),
        ("revision", "revision"),
        ("action", "action"),
        ("actor_id", "actor_id"),
        ("created_at", "created_at"),
    ):
        op.create_index(f"ix_feature_flag_revision_{name}", "feature_flag_revision", [column])


def downgrade() -> None:
    for name in ("created_at", "actor_id", "action", "revision", "flag_id"):
        op.drop_index(f"ix_feature_flag_revision_{name}", table_name="feature_flag_revision")
    op.drop_table("feature_flag_revision")
    op.drop_index("ix_feature_flag_key", table_name="feature_flag")
    op.drop_table("feature_flag")
    op.drop_index("ix_evaluation_run_started_at", table_name="evaluation_run")
    op.drop_index("ix_evaluation_run_suite_name", table_name="evaluation_run")
    op.drop_table("evaluation_run")
