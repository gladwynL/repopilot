from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator
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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("github_token", mode="before")
    @classmethod
    def blank_token_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
