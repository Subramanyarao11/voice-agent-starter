"""Add benefit version history and source freshness alerts."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0014"
down_revision = "20260808_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benefit",
        sa.Column("content_revision", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "benefit_version",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_benefit_version_benefit_version",
        "benefit_version",
        ["benefit_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_benefit_version_benefit_created",
        "benefit_version",
        ["benefit_id", "created_at"],
        unique=False,
    )
    for name, column in (
        ("benefit_id", "benefit_id"),
        ("version", "version"),
        ("action", "action"),
        ("actor_id", "actor_id"),
        ("created_at", "created_at"),
    ):
        op.create_index(f"ix_benefit_version_{name}", "benefit_version", [column])

    op.create_table(
        "source_freshness_alert",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("alert_key", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=True),
        sa.Column("dataset", sa.String(), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_key"),
    )
    op.create_index("ix_source_freshness_alert_alert_key", "source_freshness_alert", ["alert_key"])
    op.create_index(
        "ix_source_freshness_alert_benefit_id", "source_freshness_alert", ["benefit_id"]
    )
    op.create_index("ix_source_freshness_alert_dataset", "source_freshness_alert", ["dataset"])
    op.create_index(
        "ix_source_freshness_alert_alert_type", "source_freshness_alert", ["alert_type"]
    )
    op.create_index("ix_source_freshness_alert_status", "source_freshness_alert", ["status"])
    op.create_index(
        "ix_source_freshness_alert_first_seen_at",
        "source_freshness_alert",
        ["first_seen_at"],
    )
    op.create_index(
        "ix_source_freshness_alert_last_seen_at",
        "source_freshness_alert",
        ["last_seen_at"],
    )
    op.create_index(
        "ix_source_freshness_alert_status_seen",
        "source_freshness_alert",
        ["status", "last_seen_at"],
    )
    op.create_index(
        "ix_source_freshness_alert_dataset_status",
        "source_freshness_alert",
        ["dataset", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_freshness_alert_dataset_status", table_name="source_freshness_alert")
    op.drop_index("ix_source_freshness_alert_status_seen", table_name="source_freshness_alert")
    for name in (
        "last_seen_at",
        "first_seen_at",
        "status",
        "alert_type",
        "dataset",
        "benefit_id",
        "alert_key",
    ):
        op.drop_index(f"ix_source_freshness_alert_{name}", table_name="source_freshness_alert")
    op.drop_table("source_freshness_alert")
    for name in ("created_at", "actor_id", "action", "version", "benefit_id"):
        op.drop_index(f"ix_benefit_version_{name}", table_name="benefit_version")
    op.drop_index("ix_benefit_version_benefit_created", table_name="benefit_version")
    op.drop_index("ix_benefit_version_benefit_version", table_name="benefit_version")
    op.drop_table("benefit_version")
    op.drop_column("benefit", "content_revision")
