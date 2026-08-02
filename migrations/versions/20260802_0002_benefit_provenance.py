"""Add benefit verification/provenance and import manifests."""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0002"
down_revision = "20260802_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benefit",
        sa.Column(
            "verification_status",
            sa.String(length=32),
            nullable=False,
            server_default="illustrative",
        ),
    )
    op.add_column(
        "benefit",
        sa.Column("source_title", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "benefit",
        sa.Column("source_document_url", sa.String(), nullable=False, server_default=""),
    )
    op.add_column("benefit", sa.Column("source_excerpt", sa.String(), nullable=True))
    op.add_column("benefit", sa.Column("source_content_hash", sa.String(), nullable=True))
    op.add_column("benefit", sa.Column("verified_by", sa.String(), nullable=True))
    op.add_column(
        "benefit", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("benefit", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("benefit", sa.Column("valid_until", sa.Date(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE benefit SET source_document_url = source_url "
            "WHERE source_document_url = '' AND source_url <> ''"
        )
    )
    op.execute(
        sa.text(
            "UPDATE benefit SET source_title = 'Legacy source' "
            "WHERE source_title = '' AND source_url <> ''"
        )
    )
    op.create_index(
        "ix_benefit_verification_status", "benefit", ["verification_status"], unique=False
    )
    op.create_index(
        "ix_benefit_source_content_hash", "benefit", ["source_content_hash"], unique=False
    )

    op.create_table(
        "data_import_run",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("review_sample_size", sa.Integer(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["state_code"], ["state.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_import_run_source_name", "data_import_run", ["source_name"], unique=False
    )
    op.create_index(
        "ix_data_import_run_state_code", "data_import_run", ["state_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_data_import_run_state_code", table_name="data_import_run")
    op.drop_index("ix_data_import_run_source_name", table_name="data_import_run")
    op.drop_table("data_import_run")
    op.drop_index("ix_benefit_source_content_hash", table_name="benefit")
    op.drop_index("ix_benefit_verification_status", table_name="benefit")
    op.drop_column("benefit", "valid_until")
    op.drop_column("benefit", "valid_from")
    op.drop_column("benefit", "verified_at")
    op.drop_column("benefit", "verified_by")
    op.drop_column("benefit", "source_content_hash")
    op.drop_column("benefit", "source_excerpt")
    op.drop_column("benefit", "source_document_url")
    op.drop_column("benefit", "source_title")
    op.drop_column("benefit", "verification_status")
