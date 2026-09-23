from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RepoPilot API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://repopilot:repopilot@localhost:5432/repopilot"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_timeout_seconds: float = Field(default=90.0, gt=0)
    # Reasoning models spend part of this on hidden reasoning, so keep it generous.
    openai_max_output_tokens: int = Field(default=16_000, ge=1_000)
    openai_max_retries: int = Field(default=2, ge=0, le=5)

    # Estimated input tokens per model request (PR context + diffs, excluding fixed instructions).
    review_chunk_token_budget: int = Field(default=24_000, ge=8_000)
    review_max_chunks: int = Field(default=3, ge=1, le=10)
    review_max_file_tokens: int = Field(default=8_000, ge=500)
    review_min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("github_token", "openai_api_key", mode="before")
    @classmethod
    def blank_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
