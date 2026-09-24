from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

Environment = Literal["development", "test", "production"]


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RepoPilot API"
    environment: Environment = "development"
    database_url: str = "postgresql+psycopg://repopilot:repopilot@localhost:5432/repopilot"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    public_app_url: str | None = None
    """Public origin of the app, e.g. https://repopilot.example.com (OAuth callback base)."""

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
    # AI reviews running at once in this process; further cache misses get a 429.
    review_max_concurrent: int = Field(default=2, ge=1, le=20)

    # Sign-in with GitHub (separate from GITHUB_TOKEN, which is only used to read PRs).
    auth_enabled: bool = False
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: SecretStr | None = None
    auth_allowed_github_users: Annotated[list[str], NoDecode] = []
    session_secret: SecretStr | None = None
    session_max_age_seconds: int = Field(default=8 * 60 * 60, ge=300, le=7 * 24 * 60 * 60)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("auth_allowed_github_users", mode="before")
    @classmethod
    def split_allowed_users(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("auth_allowed_github_users")
    @classmethod
    def lowercase_allowed_users(cls, value: list[str]) -> list[str]:
        # GitHub logins are case-insensitive.
        return [login.lower() for login in value]

    @field_validator(
        "github_token",
        "openai_api_key",
        "github_oauth_client_secret",
        "session_secret",
        "github_oauth_client_id",
        "public_app_url",
        mode="before",
    )
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("public_app_url")
    @classmethod
    def strip_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        """Secure cookies only work over HTTPS, so follow the public URL's scheme."""
        return bool(self.public_app_url and self.public_app_url.startswith("https://"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
