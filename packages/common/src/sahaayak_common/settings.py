"""Application settings, loaded once from the environment.

Optional infrastructure is a deliberate choice: with no `DATABASE_URL` the app
uses a local SQLite file and with no reachable Redis it uses an in-process
cache. That keeps the text-mode conversation loop developable on a laptop
without Docker, while the deployed stack sets both explicitly.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward to the workspace root so paths do not depend on the cwd."""
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / ".env.example").exists():
            return candidate
    return Path.cwd()


REPO_ROOT = find_repo_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Infrastructure ---
    database_url: str | None = None
    redis_url: str | None = None

    # --- Models ---
    openai_api_key: str = ""
    openai_reasoning_model: str = "gpt-4o-mini"
    openai_structuring_model: str = "gpt-4o"
    openai_transcription_model: str = "whisper-1"
    openai_realtime_stt_enabled: bool = False
    openai_realtime_transcription_model: str = "gpt-4o-transcribe"
    # The data pipeline defaults to a conservative $10 lifetime ledger. The
    # code-level guard refuses any ceiling above $15 and persists reservations
    # across reruns, so a test command cannot reset the budget.
    openai_budget_usd: float = 10.0
    openai_budget_ledger_path: str = "data/usage/openai-budget.json"
    openai_pipeline_max_records: int = 20
    openai_pipeline_max_output_tokens: int = 1200
    openai_agent_max_output_tokens: int = 600
    openai_review_model: str = "gpt-4o-mini"
    openai_review_max_output_tokens: int = 900
    openai_review_max_input_characters: int = 16_000
    # Whisper is billed by audio duration and does not expose text-token usage
    # in the same way as chat completions. Reserve a conservative amount per
    # local transcription request so voice testing shares the same ledger.
    openai_transcription_reservation_usd: float = 0.10
    openai_vector_store_id: str = ""
    openai_rag_manifest_path: str = "data/rag/vector-store-manifest.json"
    openai_rag_answer_model: str = "gpt-4o-mini"
    openai_rag_max_results: int = 5
    openai_rag_max_output_tokens: int = 600
    openai_rag_search_reservation_usd: float = 0.01
    openai_rag_upload_reservation_usd: float = 0.0005
    openai_rag_batch_reservation_usd: float = 0.01
    # Keep a large margin below the hosted vector-store billing boundary. The
    # current corpus is far below this, but a future source expansion must not
    # silently create a large remote storage bill.
    openai_rag_max_source_bytes: int = 900_000_000
    sarvam_api_key: str = ""

    # Authorized National Career Service access is optional and deliberately
    # kept separate from the public website adapter. The admin readiness view
    # reports presence only; it never exposes the endpoint or key.
    ncs_enabled: bool = False
    ncs_api_url: str = ""
    ncs_api_key: str = ""

    # --- Tracing ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Workforce access is deliberately opt-in. The API never falls back to an
    # open admin surface when this is empty. `ADMIN_TOKENS_JSON` can hold
    # multiple token-to-role entries for local/staging operator separation.
    admin_api_token: str = ""
    admin_tokens_json: str = ""
    admin_static_tokens_enabled: bool = True
    admin_oidc_enabled: bool = False
    admin_oidc_issuer_url: str = ""
    # A deployment may need the API to reach the IdP over an internal Docker
    # hostname while tokens still carry the browser-visible issuer URL. Keep
    # discovery separate from issuer so that split-horizon networking is
    # explicit rather than hidden in the authentication code.
    admin_oidc_discovery_url: str = ""
    admin_oidc_audience: str = ""
    admin_oidc_jwks_url: str = ""
    admin_oidc_allowed_algorithms: str = "RS256"
    admin_oidc_required_amr: str = "mfa"
    admin_oidc_required_acr: str = ""
    admin_oidc_roles_claim: str = "roles"
    admin_oidc_actor_claim: str = "sub"
    admin_oidc_org_claim: str = "organization"
    admin_oidc_clock_skew_seconds: int = 60
    admin_oidc_jwks_cache_seconds: int = 3600

    # Citizen identity is deliberately separate from workforce/admin OIDC.
    # Static citizen tokens are a local/test seam only; production must use a
    # configured PKCE/OIDC BFF or approved passwordless identity provider.
    citizen_static_tokens_enabled: bool = False
    citizen_api_token: str = ""
    citizen_oidc_enabled: bool = False
    citizen_oidc_issuer_url: str = ""
    citizen_oidc_discovery_url: str = ""
    citizen_oidc_audience: str = ""
    citizen_oidc_jwks_url: str = ""
    citizen_oidc_allowed_algorithms: str = "RS256"
    citizen_oidc_subject_claim: str = "sub"
    citizen_oidc_clock_skew_seconds: int = 60
    citizen_household_dependants_enabled: bool = False
    citizen_household_max_members: int = 8
    citizen_household_retention_days: int = 730

    # Assisted Saathi sessions are short-lived and purpose-bound. The API
    # keeps the capability token hashed and requires citizen confirmation
    # before a helper projection or consequential action is available.
    assistance_invitation_ttl_minutes: int = 15
    assistance_session_ttl_minutes: int = 60
    assistance_idle_timeout_minutes: int = 10
    assistance_notice_version: str = "assisted-saathi-2026-08-09.v1"

    # Guest browser sessions stay login-free, but are still server-owned and
    # bounded. The access token is issued once and stored only in the browser
    # session; no user-supplied caller identifier authorizes a request.
    guest_session_ttl_hours: int = 24 * 30
    rate_limit_text_per_session: int = 20
    rate_limit_text_per_ip: int = 60
    rate_limit_voice_per_session: int = 3
    rate_limit_voice_per_ip: int = 10
    rate_limit_rag_per_session: int = 10
    rate_limit_rag_per_ip: int = 30
    rate_limit_session_create_per_ip: int = 10
    rate_limit_application_create_per_session: int = 10
    rate_limit_application_create_per_ip: int = 30
    rate_limit_application_status_per_session: int = 20
    rate_limit_application_status_per_ip: int = 60
    rate_limit_application_pack_per_session: int = 10
    rate_limit_application_pack_per_ip: int = 30
    rate_limit_assistance_per_session: int = 12
    rate_limit_assistance_per_ip: int = 30
    rate_limit_radar_per_session: int = 6
    rate_limit_radar_per_ip: int = 18
    rate_limit_window_seconds: int = 60
    rate_limit_key_salt: str = ""
    rate_limit_enabled: bool = True
    rate_limit_fail_closed: bool = True

    # OpenTelemetry is independently configurable from Langfuse. The endpoint
    # values follow the standard OTEL environment variable names; the base
    # endpoint is expanded to /v1/traces and /v1/metrics when used.
    otel_service_name: str = "sahaayak-api"
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_traces_endpoint: str = ""
    otel_exporter_otlp_metrics_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_console_exporter: bool = False
    otel_sample_ratio: float = 1.0

    # --- Data lifecycle ----------------------------------------------------
    # These are intentionally bounded defaults for sensitive conversation and
    # operational data. The retention command supports dry runs before a
    # deployment enables the scheduled job.
    retention_transcript_days: int = 30
    retention_telemetry_days: int = 30
    retention_audit_days: int = 365
    retention_escalation_days: int = 365
    retention_expired_session_days: int = 7

    # Department routing is fail-closed: an entry without an approved source
    # and a recent verification date is never presented as authoritative.
    department_directory_stale_days: int = 180

    # Source freshness is an operational control, not a request-side side
    # effect. The dedicated worker scans on a bounded cadence and persists
    # deduplicated alerts for the admin console. Keep the threshold and cadence
    # deployment-configurable so a production policy does not depend on a
    # developer remembering a manual command.
    freshness_stale_days: int = 90
    freshness_scan_interval_seconds: int = 3600

    # --- Infobip messaging seam --------------------------------------------
    # Every channel is off by default and gated twice: the master switch here
    # and a per-channel switch. A configured API key is never on its own taken
    # as evidence that SMS, email, or WhatsApp is actually enabled on the
    # account — those require DLT, domain, and Meta approvals this code cannot
    # verify.
    infobip_enabled: bool = False
    # Each Infobip account gets a personalized base URL. It is configuration,
    # not a secret; the API key is the secret.
    infobip_base_url: str = ""
    infobip_api_key: str = ""
    infobip_environment: str = "development"

    infobip_sms_enabled: bool = False
    infobip_sms_sender: str = ""

    infobip_whatsapp_enabled: bool = False
    infobip_whatsapp_sender: str = ""

    infobip_email_enabled: bool = False
    infobip_email_sender: str = ""
    infobip_email_sender_name: str = "Sahaayak"

    infobip_voice_enabled: bool = False
    infobip_voice_number: str = ""
    infobip_calls_configuration_id: str = ""
    infobip_calls_subscription_id: str = ""

    infobip_webhook_auth_secret: str = ""
    infobip_request_timeout_seconds: float = 10.0
    infobip_max_retries: int = 2
    infobip_max_webhook_bytes: int = 256 * 1024
    # Telecom and messaging charges are billed in local currency, so the
    # Infobip ledger is kept in minor units with an explicit ISO code rather
    # than reusing the OpenAI USD ledger.
    infobip_cost_currency: str = "INR"
    infobip_daily_budget_minor_units: int | None = None
    infobip_monthly_budget_minor_units: int | None = None

    # Contact destinations are encrypted at rest with this key. External
    # channels refuse to enable without it rather than falling back to storing
    # a phone number in plaintext.
    infobip_contact_encryption_key: str = ""

    # Application references (acknowledgement numbers, application IDs) are
    # encrypted separately from messaging destinations. The manual status
    # workflow can still be used without this key when no reference is saved;
    # reference capture fails closed until deployment supplies it.
    application_data_encryption_key: str = ""
    profile_data_encryption_key: str = ""
    profile_hash_key: str = ""
    citizen_identity_hash_key: str = ""

    # A single outbound message can only cost so much before something is
    # wrong with the template. Unicode Kannada/Hindi text costs roughly one
    # segment per 67 characters, so this is a small number of segments.
    sms_max_segments: int = 4
    contact_verification_code_ttl_seconds: int = 600
    contact_verification_max_attempts: int = 5
    rate_limit_contact_verify_per_session: int = 5
    rate_limit_contact_verify_per_ip: int = 20
    rate_limit_feedback_per_session: int = 5
    rate_limit_feedback_per_ip: int = 20

    # --- Telephony seam ----------------------------------------------------
    # The generic signed webhook is disabled until a telephony provider and
    # webhook secret are configured. Browser callers never use this path.
    telephony_enabled: bool = False
    telephony_webhook_secret: str = ""
    telephony_provider: str = "generic"
    telephony_max_timestamp_skew_seconds: int = 300

    # --- Application ---
    env: str = "development"
    log_json: bool = False
    default_language: str = "kn"
    default_state: str = "KA"
    web_base_url: str = "http://localhost:5173"

    # A verdict below this is offered to a human instead of being read out as
    # fact. See docs/spec-v2.md on escalation.
    escalation_confidence_threshold: float = 0.7
    escalation_sla_hours: int = 24

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{REPO_ROOT / 'data' / 'sahaayak.db'}"

    @property
    def resolved_openai_budget_ledger_path(self) -> Path:
        path = Path(self.openai_budget_ledger_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def resolved_openai_rag_manifest_path(self) -> Path:
        path = Path(self.openai_rag_manifest_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def resolved_openai_vector_store_id(self) -> str:
        """Use explicit deployment configuration, then the local sync record."""
        if self.openai_vector_store_id.strip():
            return self.openai_vector_store_id.strip()
        manifest_path = self.resolved_openai_rag_manifest_path
        if not manifest_path.exists():
            return ""
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        vector_store_id = payload.get("vector_store_id") if isinstance(payload, dict) else ""
        return vector_store_id if isinstance(vector_store_id, str) else ""

    @property
    def using_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def is_development(self) -> bool:
        return self.env == "development"

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    @property
    def llm_enabled(self) -> bool:
        """Without a key the agent falls back to rule-based understanding."""
        return bool(self.openai_api_key)

    @property
    def tts_enabled(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def infobip_configured(self) -> bool:
        """Credentials are present. Says nothing about channel entitlement."""
        return bool(self.infobip_base_url.strip() and self.infobip_api_key.strip())

    @property
    def infobip_ready(self) -> bool:
        return self.infobip_enabled and self.infobip_configured

    @property
    def contact_encryption_configured(self) -> bool:
        return bool(self.infobip_contact_encryption_key.strip())

    def infobip_channel_ready(self, channel: str) -> bool:
        """Whether one channel may be attempted at all.

        Deliberately conservative: an external channel also needs somewhere to
        store its destination safely, so a missing encryption key disables the
        channel rather than degrading how the contact is stored.
        """
        if not self.infobip_ready or not self.contact_encryption_configured:
            return False
        return {
            "sms": self.infobip_sms_enabled and bool(self.infobip_sms_sender.strip()),
            "email": self.infobip_email_enabled and bool(self.infobip_email_sender.strip()),
            "whatsapp": (
                self.infobip_whatsapp_enabled and bool(self.infobip_whatsapp_sender.strip())
            ),
            "voice": self.infobip_voice_enabled and bool(self.infobip_voice_number.strip()),
        }.get(channel, False)

    @property
    def otel_enabled(self) -> bool:
        return bool(
            self.otel_console_exporter
            or self.otel_exporter_otlp_endpoint
            or self.otel_exporter_otlp_traces_endpoint
            or self.otel_exporter_otlp_metrics_endpoint
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
