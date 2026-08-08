"""Add namespaced metadata for job postings.

Job records continue to use the Benefit table and the deterministic matcher.
This additive JSON column holds posting-specific values such as an
advertisement number, employer, vacancy count, publication date, deadline,
pay-scale text, and application URL without making scheme rows carry a set of
job-only nullable columns.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260808_0010"
down_revision = "20260803_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("benefit", sa.Column("job_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("benefit", "job_metadata")
