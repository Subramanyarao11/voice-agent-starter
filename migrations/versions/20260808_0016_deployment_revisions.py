"""Capture safe deployment metadata for comparison and rollback review."""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0016"
down_revision = "20260808_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployment_revision",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("release_key", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("app_version", sa.String(), nullable=False),
        sa.Column("git_commit_sha", sa.String(), nullable=False),
        sa.Column("image_digest", sa.String(), nullable=False),
        sa.Column("migration_revision", sa.String(), nullable=True),
        sa.Column("data_revision", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("active_flags", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_key"),
    )
    op.create_index("ix_deployment_revision_release_key", "deployment_revision", ["release_key"])
    op.create_index(
        "ix_deployment_revision_environment", "deployment_revision", ["environment"]
    )
    op.create_index(
        "ix_deployment_revision_deployed_at", "deployment_revision", ["deployed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_deployment_revision_deployed_at", table_name="deployment_revision")
    op.drop_index("ix_deployment_revision_environment", table_name="deployment_revision")
    op.drop_index("ix_deployment_revision_release_key", table_name="deployment_revision")
    op.drop_table("deployment_revision")
