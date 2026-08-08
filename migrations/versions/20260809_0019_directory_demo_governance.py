"""Add enriched department records and immutable directory governance."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0019"
down_revision = "20260809_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "department_directory_entry",
        sa.Column("valid_until", sa.Date(), nullable=True),
    )
    op.add_column(
        "department_directory_entry",
        sa.Column("working_hours", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "department_directory_entry",
        sa.Column(
            "supported_languages",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "department_directory_entry",
        sa.Column("coverage_basis", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "department_directory_entry",
        sa.Column("content_revision", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "department_directory_version",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["department_directory_entry.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_department_directory_version_id", ["id"]),
        ("ix_department_directory_version_entry_id", ["entry_id"]),
        ("ix_department_directory_version_version", ["version"]),
        ("ix_department_directory_version_action", ["action"]),
        ("ix_department_directory_version_actor_id", ["actor_id"]),
        ("ix_department_directory_version_created_at", ["created_at"]),
        (
            "ix_department_directory_version_entry_version",
            ["entry_id", "version"],
        ),
        (
            "ix_department_directory_version_entry_created",
            ["entry_id", "created_at"],
        ),
    ):
        op.create_index(
            name,
            "department_directory_version",
            columns,
            unique=name.endswith("entry_version"),
        )


def downgrade() -> None:
    for name in (
        "ix_department_directory_version_entry_created",
        "ix_department_directory_version_entry_version",
        "ix_department_directory_version_created_at",
        "ix_department_directory_version_actor_id",
        "ix_department_directory_version_action",
        "ix_department_directory_version_version",
        "ix_department_directory_version_entry_id",
        "ix_department_directory_version_id",
    ):
        op.drop_index(name, table_name="department_directory_version")
    op.drop_table("department_directory_version")
    for name in (
        "content_revision",
        "coverage_basis",
        "supported_languages",
        "working_hours",
        "valid_until",
    ):
        op.drop_column("department_directory_entry", name)
