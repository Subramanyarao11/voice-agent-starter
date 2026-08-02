"""Application settings, loaded once from the environment.

Optional infrastructure is a deliberate choice: with no `DATABASE_URL` the app
uses a local SQLite file and with no reachable Redis it uses an in-process
cache. That keeps the text-mode conversation loop developable on a laptop
without Docker, while the deployed stack sets both explicitly.
"""

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
    def using_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def is_development(self) -> bool:
        return self.env == "development"

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
