"""Add source-attested department routing records."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0017"
down_revision = "20260808_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "department_directory_entry",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entry_key", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=False),
        sa.Column("district_code", sa.String(), nullable=False),
        sa.Column("district_name", sa.String(), nullable=False),
        sa.Column("service_domain", sa.String(), nullable=False),
        sa.Column("pincode", sa.String(), nullable=False),
        sa.Column("pincode_prefix", sa.String(), nullable=False),
        sa.Column("department_code", sa.String(), nullable=False),
        sa.Column("department_name", sa.String(), nullable=False),
        sa.Column("help_centre_name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("website_url", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_record_id", sa.String(), nullable=False),
        sa.Column("source_last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_status", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["state_code"], ["state.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_key"),
    )
    for name, columns in (
        ("ix_department_directory_entry_key", ["entry_key"]),
        ("ix_department_directory_state_code", ["state_code"]),
        ("ix_department_directory_district_name", ["district_name"]),
        ("ix_department_directory_service_domain", ["service_domain"]),
        ("ix_department_directory_pincode", ["pincode"]),
        ("ix_department_directory_pincode_prefix", ["pincode_prefix"]),
        ("ix_department_directory_approval_status", ["approval_status"]),
        ("ix_department_directory_is_active", ["is_active"]),
        ("ix_department_directory_created_at", ["created_at"]),
        (
            "ix_department_directory_state_service_status",
            ["state_code", "service_domain", "approval_status", "is_active"],
        ),
        (
            "ix_department_directory_district_service_status",
            [
                "state_code",
                "district_name",
                "service_domain",
                "approval_status",
                "is_active",
            ],
        ),
        (
            "ix_department_directory_pincode_service_status",
            ["pincode", "service_domain", "approval_status", "is_active"],
        ),
        (
            "ix_department_directory_prefix_service_status",
            ["pincode_prefix", "service_domain", "approval_status", "is_active"],
        ),
    ):
        op.create_index(name, "department_directory_entry", columns)

    with op.batch_alter_table("escalation_ticket") as batch:
        batch.add_column(sa.Column("routing_directory_entry_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("routing_source_url", sa.String(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("routing_verified_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index(
            "ix_escalation_ticket_routing_directory_entry_id",
            ["routing_directory_entry_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("escalation_ticket") as batch:
        batch.drop_index("ix_escalation_ticket_routing_directory_entry_id")
        batch.drop_column("routing_verified_at")
        batch.drop_column("routing_source_url")
        batch.drop_column("routing_directory_entry_id")

    for name in (
        "ix_department_directory_prefix_service_status",
        "ix_department_directory_pincode_service_status",
        "ix_department_directory_district_service_status",
        "ix_department_directory_state_service_status",
        "ix_department_directory_created_at",
        "ix_department_directory_is_active",
        "ix_department_directory_approval_status",
        "ix_department_directory_pincode_prefix",
        "ix_department_directory_pincode",
        "ix_department_directory_service_domain",
        "ix_department_directory_district_name",
        "ix_department_directory_state_code",
        "ix_department_directory_entry_key",
    ):
        op.drop_index(name, table_name="department_directory_entry")
    op.drop_table("department_directory_entry")
