"""Add citizen ownership columns to application checklist tasks."""

import sqlalchemy as sa
from alembic import op


revision = "20260809_0026"
down_revision = "20260809_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ApplicationTask was created before the household/account migration. The
    # model later gained these nullable ownership fields, but the original
    # table migration was not amended. Keep the fields nullable so existing
    # guest rows remain valid and can be migrated explicitly when a citizen
    # account is linked.
    with op.batch_alter_table("application_task") as batch:
        batch.add_column(sa.Column("citizen_account_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("household_member_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_application_task_citizen_account_id",
            "citizen_account",
            ["citizen_account_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_application_task_household_member_id",
            "household_member",
            ["household_member_id"],
            ["id"],
        )
        batch.create_index(
            "ix_application_task_citizen_account_id",
            ["citizen_account_id"],
        )
        batch.create_index(
            "ix_application_task_household_member_id",
            ["household_member_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("application_task") as batch:
        batch.drop_index("ix_application_task_household_member_id")
        batch.drop_index("ix_application_task_citizen_account_id")
        batch.drop_constraint("fk_application_task_household_member_id", type_="foreignkey")
        batch.drop_constraint("fk_application_task_citizen_account_id", type_="foreignkey")
        batch.drop_column("household_member_id")
        batch.drop_column("citizen_account_id")
