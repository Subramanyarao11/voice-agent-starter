"""Add encrypted opaque citizen OIDC/BFF browser sessions."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0024"
down_revision = "20260809_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "citizen_auth_session",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("citizen_account_id", sa.String(), nullable=False),
        sa.Column("session_token_hash", sa.String(), nullable=False),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["citizen_account_id"], ["citizen_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    for name, columns in (
        ("ix_citizen_auth_session_citizen_account_id", ["citizen_account_id"]),
        ("ix_citizen_auth_session_session_token_hash", ["session_token_hash"]),
        ("ix_citizen_auth_session_access_token_expires_at", ["access_token_expires_at"]),
        ("ix_citizen_auth_session_created_at", ["created_at"]),
        ("ix_citizen_auth_session_last_used_at", ["last_used_at"]),
        ("ix_citizen_auth_session_revoked_at", ["revoked_at"]),
        (
            "ix_citizen_auth_session_account_active",
            ["citizen_account_id", "revoked_at"],
        ),
        (
            "ix_citizen_auth_session_expiry",
            ["access_token_expires_at", "revoked_at"],
        ),
    ):
        op.create_index(name, "citizen_auth_session", columns)


def downgrade() -> None:
    for name in (
        "ix_citizen_auth_session_expiry",
        "ix_citizen_auth_session_account_active",
        "ix_citizen_auth_session_revoked_at",
        "ix_citizen_auth_session_last_used_at",
        "ix_citizen_auth_session_created_at",
        "ix_citizen_auth_session_access_token_expires_at",
        "ix_citizen_auth_session_session_token_hash",
        "ix_citizen_auth_session_citizen_account_id",
    ):
        op.drop_index(name, table_name="citizen_auth_session")
    op.drop_table("citizen_auth_session")
