"""Add guest session credentials, trace correlation, and provider policies."""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0006"
down_revision = "20260802_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_session", sa.Column("access_token_hash", sa.String(), nullable=True))
    op.add_column(
        "user_session",
        sa.Column("auth_mode", sa.String(), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "user_session", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_user_session_access_token_hash",
        "user_session",
        ["access_token_hash"],
        unique=True,
    )
    op.create_index("ix_user_session_auth_mode", "user_session", ["auth_mode"])
    op.create_index("ix_user_session_expires_at", "user_session", ["expires_at"])

    op.add_column("telemetry_event", sa.Column("trace_id", sa.String(), nullable=True))
    op.add_column("telemetry_event", sa.Column("trace_url", sa.String(), nullable=True))
    op.create_index("ix_telemetry_event_trace_id", "telemetry_event", ["trace_id"])

    op.create_table(
        "provider_policy",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("primary_provider", sa.String(), nullable=False),
        sa.Column("fallback_provider", sa.String(), nullable=True),
        sa.Column("circuit_state", sa.String(), nullable=False),
        sa.Column("daily_budget_usd", sa.Float(), nullable=True),
        sa.Column("monthly_budget_usd", sa.Float(), nullable=True),
        sa.Column("override_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_policy_provider", "provider_policy", ["provider"])
    op.create_index("ix_provider_policy_scope", "provider_policy", ["scope"])
    op.create_index(
        "ix_provider_policy_provider_scope",
        "provider_policy",
        ["provider", "scope"],
        unique=True,
    )

    op.create_table(
        "provider_policy_revision",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["provider_policy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("policy_id", "policy_id"),
        ("revision", "revision"),
        ("action", "action"),
        ("actor_id", "actor_id"),
        ("created_at", "created_at"),
    ):
        op.create_index(f"ix_provider_policy_revision_{name}", "provider_policy_revision", [column])


def downgrade() -> None:
    for name in ("created_at", "actor_id", "action", "revision", "policy_id"):
        op.drop_index(f"ix_provider_policy_revision_{name}", table_name="provider_policy_revision")
    op.drop_table("provider_policy_revision")
    op.drop_index("ix_provider_policy_provider_scope", table_name="provider_policy")
    op.drop_index("ix_provider_policy_scope", table_name="provider_policy")
    op.drop_index("ix_provider_policy_provider", table_name="provider_policy")
    op.drop_table("provider_policy")
    op.drop_index("ix_telemetry_event_trace_id", table_name="telemetry_event")
    op.drop_column("telemetry_event", "trace_url")
    op.drop_column("telemetry_event", "trace_id")
    op.drop_index("ix_user_session_expires_at", table_name="user_session")
    op.drop_index("ix_user_session_auth_mode", table_name="user_session")
    op.drop_index("ix_user_session_access_token_hash", table_name="user_session")
    op.drop_column("user_session", "expires_at")
    op.drop_column("user_session", "auth_mode")
    op.drop_column("user_session", "access_token_hash")
