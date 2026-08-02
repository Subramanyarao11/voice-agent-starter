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
    # The data pipeline defaults to a conservative $10 lifetime ledger. The
    # code-level guard refuses any ceiling above $15 and persists reservations
    # across reruns, so a test command cannot reset the budget.
    openai_budget_usd: float = 10.0
    openai_budget_ledger_path: str = "data/usage/openai-budget.json"
    openai_pipeline_max_records: int = 20
    openai_pipeline_max_output_tokens: int = 1200
    openai_agent_max_output_tokens: int = 600
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

    # --- Tracing ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Application ---
    env: str = "development"
    log_json: bool = False
    default_language: str = "kn"
    default_state: str = "KA"
    web_base_url: str = "http://localhost:5173"

    # A verdict below this is offered to a human instead of being read out as
    # fact. See docs/spec-v2.md on escalation.
    escalation_confidence_threshold: float = 0.7

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
