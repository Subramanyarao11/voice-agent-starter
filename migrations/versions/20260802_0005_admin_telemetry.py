"""Add redacted telemetry and append-only workforce audit events."""

import sqlalchemy as sa
from alembic import op

revision = "20260802_0005"
down_revision = "20260802_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("language_code", sa.String(), nullable=True),
        sa.Column("state_code", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("event_type", "event_type"),
        ("request_id", "request_id"),
        ("route", "route"),
        ("status_code", "status_code"),
        ("surface", "surface"),
        ("language_code", "language_code"),
        ("state_code", "state_code"),
        ("provider", "provider"),
        ("created_at", "created_at"),
    ):
        op.create_index(f"ix_telemetry_event_{name}", "telemetry_event", [column])

    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("safe_before", sa.JSON(), nullable=False),
        sa.Column("safe_after", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("actor_id", "actor_id"),
        ("actor_role", "actor_role"),
        ("action", "action"),
        ("target_type", "target_type"),
        ("target_id", "target_id"),
        ("request_id", "request_id"),
        ("created_at", "created_at"),
    ):
        op.create_index(f"ix_audit_event_{name}", "audit_event", [column])


def downgrade() -> None:
    for name in (
        "created_at",
        "request_id",
        "target_id",
        "target_type",
        "action",
        "actor_role",
        "actor_id",
    ):
        op.drop_index(f"ix_audit_event_{name}", table_name="audit_event")
    op.drop_table("audit_event")

    for name in (
        "created_at",
        "provider",
        "state_code",
        "language_code",
        "surface",
        "status_code",
        "route",
        "request_id",
        "event_type",
    ):
        op.drop_index(f"ix_telemetry_event_{name}", table_name="telemetry_event")
    op.drop_table("telemetry_event")
