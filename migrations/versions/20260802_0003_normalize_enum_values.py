"""Normalize legacy enum-like strings to their public wire values."""

from alembic import op

revision = "20260802_0003"
down_revision = "20260802_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older SQLModel/SQLAlchemy mappings stored enum member names (SCHEME),
    # while the current contract deliberately exposes values (scheme). The
    # provenance migration also introduced a lowercase server default, so
    # normalize both columns before the ORM starts reading them.
    op.execute("UPDATE benefit SET domain = lower(domain) WHERE domain IS NOT NULL")
    op.execute(
        "UPDATE benefit SET verification_status = lower(verification_status) "
        "WHERE verification_status IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE benefit SET domain = upper(domain) WHERE domain IS NOT NULL")
    op.execute(
        "UPDATE benefit SET verification_status = upper(verification_status) "
        "WHERE verification_status IS NOT NULL"
    )
