"""Add citizen account and household radar foundation tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0022"
down_revision = "20260809_0021"
branch_labels = None
depends_on = None


def _indexes(table: str, entries: list[tuple[str, list[str], bool | None]]) -> None:
    for name, columns, unique in entries:
        op.create_index(name, table, columns, unique=unique if unique is not None else False)


def upgrade() -> None:
    op.create_table(
        "citizen_account",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("identity_provider", sa.String(), nullable=False),
        sa.Column("provider_subject_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("preferred_language_code", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("terms_version", sa.String(), nullable=False),
        sa.Column("privacy_notice_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["preferred_language_code"], ["language.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_subject_hash"),
    )
    _indexes(
        "citizen_account",
        [
            ("ix_citizen_account_identity_provider", ["identity_provider"], None),
            ("ix_citizen_account_provider_subject_hash", ["provider_subject_hash"], None),
            ("ix_citizen_account_status", ["status"], None),
            ("ix_citizen_account_created_at", ["created_at"], None),
        ],
    )

    op.create_table(
        "household",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_account_id", sa.String(), nullable=False),
        sa.Column("label_ciphertext", sa.String(), nullable=True),
        sa.Column("label_masked", sa.String(), nullable=False),
        sa.Column("state_code", sa.String(), nullable=True),
        sa.Column("district", sa.String(), nullable=False),
        sa.Column("pincode_ciphertext", sa.String(), nullable=True),
        sa.Column("pincode_masked", sa.String(), nullable=False),
        sa.Column("pincode_prefix", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("matching_policy_version", sa.String(), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_account_id"], ["citizen_account.id"]),
        sa.ForeignKeyConstraint(["state_code"], ["state.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "household",
        [
            ("ix_household_owner_account_id", ["owner_account_id"], None),
            ("ix_household_state_code", ["state_code"], None),
            ("ix_household_pincode_prefix", ["pincode_prefix"], None),
            ("ix_household_status", ["status"], None),
            ("ix_household_created_at", ["created_at"], None),
            ("ix_household_owner_status", ["owner_account_id", "status"], None),
        ],
    )

    op.create_table(
        "household_member",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("alias_ciphertext", sa.String(), nullable=True),
        sa.Column("alias_masked", sa.String(), nullable=False),
        sa.Column("safe_ordinal", sa.String(), nullable=False),
        sa.Column("relationship_category", sa.String(), nullable=False),
        sa.Column("is_account_owner_subject", sa.Boolean(), nullable=False),
        sa.Column("age_class", sa.String(), nullable=False),
        sa.Column("authority_status", sa.String(), nullable=False),
        sa.Column("authority_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "household_member",
        [
            ("ix_household_member_household_id", ["household_id"], None),
            ("ix_household_member_status", ["status"], None),
            ("ix_household_member_created_at", ["created_at"], None),
            ("ix_household_member_household_status", ["household_id", "status"], None),
        ],
    )

    op.create_table(
        "profile_fact_definition",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("fact_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("data_type", sa.String(), nullable=False),
        sa.Column("allowed_values", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("sensitivity", sa.String(), nullable=False),
        sa.Column("allowed_purposes", sa.JSON(), nullable=False),
        sa.Column("inheritance_allowed", sa.Boolean(), nullable=False),
        sa.Column("reconfirmation_days", sa.Integer(), nullable=True),
        sa.Column("question", sa.JSON(), nullable=False),
        sa.Column("help_text", sa.JSON(), nullable=False),
        sa.Column("matcher_slot", sa.String(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "profile_fact_definition",
        [
            ("ix_profile_fact_definition_fact_key", ["fact_key"], None),
            ("ix_profile_fact_definition_review_status", ["review_status"], None),
            ("ix_profile_fact_definition_key_version", ["fact_key", "version"], True),
            ("ix_profile_fact_definition_status", ["review_status", "fact_key"], None),
        ],
    )

    op.create_table(
        "profile_fact",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("household_member_id", sa.String(), nullable=True),
        sa.Column("fact_key", sa.String(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("value_ciphertext", sa.String(), nullable=False),
        sa.Column("value_hash", sa.String(), nullable=False),
        sa.Column("masked_value", sa.String(), nullable=False),
        sa.Column("value_source", sa.String(), nullable=False),
        sa.Column("purposes", sa.JSON(), nullable=False),
        sa.Column("confirmed_by", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconfirm_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.ForeignKeyConstraint(["household_member_id"], ["household_member.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "profile_fact",
        [
            ("ix_profile_fact_household_id", ["household_id"], None),
            ("ix_profile_fact_household_member_id", ["household_member_id"], None),
            ("ix_profile_fact_fact_key", ["fact_key"], None),
            ("ix_profile_fact_value_hash", ["value_hash"], None),
            ("ix_profile_fact_status", ["status"], None),
            (
                "ix_profile_fact_member_key_current",
                ["household_member_id", "fact_key", "status"],
                True,
            ),
            ("ix_profile_fact_household_key_current", ["household_id", "fact_key", "status"], None),
        ],
    )

    op.create_table(
        "profile_fact_revision",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_fact_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("before_masked_value", sa.String(), nullable=False),
        sa.Column("after_masked_value", sa.String(), nullable=False),
        sa.Column("value_hash", sa.String(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_fact_id"], ["profile_fact.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "profile_fact_revision",
        [
            ("ix_profile_fact_revision_profile_fact_id", ["profile_fact_id"], None),
            ("ix_profile_fact_revision_created_at", ["created_at"], None),
        ],
    )

    op.create_table(
        "life_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("household_member_id", sa.String(), nullable=True),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("occurred_precision", sa.String(), nullable=False),
        sa.Column("attributes_ciphertext", sa.String(), nullable=True),
        sa.Column("attributes_hash", sa.String(), nullable=False),
        sa.Column("provenance", sa.String(), nullable=False),
        sa.Column("confirmed_by", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("supersedes_event_id", sa.String(), nullable=True),
        sa.Column("affected_domains", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.ForeignKeyConstraint(["household_member_id"], ["household_member.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "life_event",
        [
            ("ix_life_event_household_id", ["household_id"], None),
            ("ix_life_event_household_member_id", ["household_member_id"], None),
            ("ix_life_event_event_key", ["event_key"], None),
            ("ix_life_event_status", ["status"], None),
            ("ix_life_event_created_at", ["created_at"], None),
            ("ix_life_event_household_member_status", ["household_member_id", "status"], None),
        ],
    )

    op.create_table(
        "member_recommendation",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=False),
        sa.Column("household_member_id", sa.String(), nullable=False),
        sa.Column("benefit_id", sa.String(), nullable=False),
        sa.Column("benefit_revision", sa.Integer(), nullable=False),
        sa.Column("matcher_rules_version", sa.String(), nullable=False),
        sa.Column("computed_profile_version", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("criterion_evidence", sa.JSON(), nullable=False),
        sa.Column("fact_use_evidence", sa.JSON(), nullable=False),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.Column("trigger_reference_hash", sa.String(), nullable=False),
        sa.Column("first_generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissal_reason_code", sa.String(), nullable=True),
        sa.Column("linked_saved_benefit_id", sa.String(), nullable=True),
        sa.Column("linked_application_case_id", sa.String(), nullable=True),
        sa.Column("source_deadline", sa.Date(), nullable=True),
        sa.Column("source_last_verified_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.ForeignKeyConstraint(["household_member_id"], ["household_member.id"]),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit.id"]),
        sa.ForeignKeyConstraint(["linked_saved_benefit_id"], ["saved_benefit.id"]),
        sa.ForeignKeyConstraint(["linked_application_case_id"], ["application_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "member_recommendation",
        [
            ("ix_member_recommendation_household_id", ["household_id"], None),
            ("ix_member_recommendation_household_member_id", ["household_member_id"], None),
            ("ix_member_recommendation_benefit_id", ["benefit_id"], None),
            ("ix_member_recommendation_state", ["state"], None),
            (
                "ix_member_recommendation_member_benefit_revision",
                ["household_member_id", "benefit_id", "benefit_revision"],
                True,
            ),
            ("ix_member_recommendation_member_state", ["household_member_id", "state"], None),
        ],
    )

    op.create_table(
        "household_consent_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("citizen_account_id", sa.String(), nullable=False),
        sa.Column("household_id", sa.String(), nullable=True),
        sa.Column("household_member_id", sa.String(), nullable=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("notice_version", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("assistance_session_id", sa.String(), nullable=True),
        sa.Column("safe_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["citizen_account_id"], ["citizen_account.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.ForeignKeyConstraint(["household_member_id"], ["household_member.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "household_consent_event",
        [
            ("ix_household_consent_event_citizen_account_id", ["citizen_account_id"], None),
            ("ix_household_consent_event_household_id", ["household_id"], None),
            ("ix_household_consent_event_household_member_id", ["household_member_id"], None),
            ("ix_household_consent_event_purpose", ["purpose"], None),
            ("ix_household_consent_event_action", ["action"], None),
            ("ix_household_consent_event_created_at", ["created_at"], None),
        ],
    )

    op.create_table(
        "guest_migration",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("guest_session_id", sa.String(), nullable=False),
        sa.Column("citizen_account_id", sa.String(), nullable=False),
        sa.Column("selected_object_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("conflict_report", sa.JSON(), nullable=False),
        sa.Column("source_deletion_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guest_session_id"], ["user_session.id"]),
        sa.ForeignKeyConstraint(["citizen_account_id"], ["citizen_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "guest_migration",
        [
            ("ix_guest_migration_guest_session_id", ["guest_session_id"], None),
            ("ix_guest_migration_citizen_account_id", ["citizen_account_id"], None),
            ("ix_guest_migration_status", ["status"], None),
            ("ix_guest_migration_account_status", ["citizen_account_id", "status"], None),
            ("ix_guest_migration_idempotency", ["citizen_account_id", "idempotency_key"], True),
        ],
    )

    for table in ("saved_benefit", "application_case", "reminder"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("citizen_account_id", sa.String(), nullable=True))
            batch.add_column(sa.Column("household_member_id", sa.String(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_citizen_account_id",
                "citizen_account",
                ["citizen_account_id"],
                ["id"],
            )
            batch.create_foreign_key(
                f"fk_{table}_household_member_id",
                "household_member",
                ["household_member_id"],
                ["id"],
            )
            batch.create_index(f"ix_{table}_citizen_account_id", ["citizen_account_id"])
            batch.create_index(f"ix_{table}_household_member_id", ["household_member_id"])


def downgrade() -> None:
    for table in ("saved_benefit", "application_case", "reminder"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_household_member_id")
            batch.drop_index(f"ix_{table}_citizen_account_id")
            batch.drop_constraint(f"fk_{table}_household_member_id", type_="foreignkey")
            batch.drop_constraint(f"fk_{table}_citizen_account_id", type_="foreignkey")
            batch.drop_column("household_member_id")
            batch.drop_column("citizen_account_id")

    for table, names in (
        (
            "guest_migration",
            (
                "ix_guest_migration_idempotency",
                "ix_guest_migration_account_status",
                "ix_guest_migration_status",
                "ix_guest_migration_citizen_account_id",
                "ix_guest_migration_guest_session_id",
            ),
        ),
        (
            "household_consent_event",
            (
                "ix_household_consent_event_created_at",
                "ix_household_consent_event_action",
                "ix_household_consent_event_purpose",
                "ix_household_consent_event_household_member_id",
                "ix_household_consent_event_household_id",
                "ix_household_consent_event_citizen_account_id",
            ),
        ),
        (
            "member_recommendation",
            (
                "ix_member_recommendation_member_state",
                "ix_member_recommendation_member_benefit_revision",
                "ix_member_recommendation_state",
                "ix_member_recommendation_benefit_id",
                "ix_member_recommendation_household_member_id",
                "ix_member_recommendation_household_id",
            ),
        ),
        (
            "life_event",
            (
                "ix_life_event_household_member_status",
                "ix_life_event_created_at",
                "ix_life_event_status",
                "ix_life_event_event_key",
                "ix_life_event_household_member_id",
                "ix_life_event_household_id",
            ),
        ),
        (
            "profile_fact_revision",
            ("ix_profile_fact_revision_created_at", "ix_profile_fact_revision_profile_fact_id"),
        ),
        (
            "profile_fact",
            (
                "ix_profile_fact_household_key_current",
                "ix_profile_fact_member_key_current",
                "ix_profile_fact_status",
                "ix_profile_fact_value_hash",
                "ix_profile_fact_fact_key",
                "ix_profile_fact_household_member_id",
                "ix_profile_fact_household_id",
            ),
        ),
        (
            "profile_fact_definition",
            (
                "ix_profile_fact_definition_status",
                "ix_profile_fact_definition_key_version",
                "ix_profile_fact_definition_review_status",
                "ix_profile_fact_definition_fact_key",
            ),
        ),
        (
            "household_member",
            (
                "ix_household_member_household_status",
                "ix_household_member_created_at",
                "ix_household_member_status",
                "ix_household_member_household_id",
            ),
        ),
        (
            "household",
            (
                "ix_household_owner_status",
                "ix_household_created_at",
                "ix_household_status",
                "ix_household_pincode_prefix",
                "ix_household_state_code",
                "ix_household_owner_account_id",
            ),
        ),
        (
            "citizen_account",
            (
                "ix_citizen_account_created_at",
                "ix_citizen_account_status",
                "ix_citizen_account_provider_subject_hash",
                "ix_citizen_account_identity_provider",
            ),
        ),
    ):
        for name in names:
            op.drop_index(name, table_name=table)
        op.drop_table(table)
