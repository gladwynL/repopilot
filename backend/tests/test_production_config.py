import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.production import ConfigurationError, configuration_problems, validate_settings
from app.main import create_app

SECRETS = {
    "openai_api_key": "sk-prod-sentinel-openai",
    "github_oauth_client_secret": "oauth-sentinel-client-secret",
    "session_secret": "session-sentinel-" + "x" * 40,
}


def production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://rp_app:db-sentinel-password@db.internal:5432/repopilot",
        "public_app_url": "https://repopilot.example.com",
        "cors_origins": "",
        "auth_enabled": True,
        "github_oauth_client_id": "Iv1.example",
        "auth_allowed_github_users": "gladwynL",
        **SECRETS,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_local_defaults_are_accepted() -> None:
    assert configuration_problems(Settings()) == []


def test_complete_production_settings_are_accepted() -> None:
    validate_settings(production())


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"auth_enabled": False}, "AUTH_ENABLED"),
        ({"github_oauth_client_id": ""}, "GITHUB_OAUTH_CLIENT_ID"),
        ({"github_oauth_client_secret": ""}, "GITHUB_OAUTH_CLIENT_SECRET"),
        ({"session_secret": "too-short"}, "SESSION_SECRET"),
        ({"auth_allowed_github_users": ""}, "AUTH_ALLOWED_GITHUB_USERS"),
        ({"public_app_url": ""}, "PUBLIC_APP_URL"),
        ({"public_app_url": "http://repopilot.example.com"}, "PUBLIC_APP_URL"),
        ({"openai_api_key": ""}, "OPENAI_API_KEY"),
        (
            {"database_url": "postgresql+psycopg://repopilot:repopilot@db:5432/repopilot"},
            "DATABASE_URL",
        ),
        ({"database_url": "postgresql+psycopg://u:p@localhost:5432/x"}, "DATABASE_URL"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
    ],
)
def test_missing_or_unsafe_production_setting_is_rejected(
    override: dict[str, object], expected: str
) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(production(**override))

    assert expected in str(exc_info.value)


def test_error_names_settings_but_never_includes_values() -> None:
    settings = production(auth_enabled=False, session_secret="short-sentinel")

    with pytest.raises(ConfigurationError) as exc_info:
        validate_settings(settings)

    message = str(exc_info.value)
    for value in [*SECRETS.values(), "short-sentinel", "db-sentinel-password"]:
        assert value not in message


def test_enabling_auth_locally_requires_oauth_configuration() -> None:
    problems = configuration_problems(Settings(auth_enabled=True))

    assert any("GITHUB_OAUTH_CLIENT_ID" in p for p in problems)
    assert any("SESSION_SECRET" in p for p in problems)


def test_app_refuses_to_start_with_invalid_production_config() -> None:
    with pytest.raises(ConfigurationError):
        create_app(production(openai_api_key=""))


def test_docs_are_disabled_in_production() -> None:
    with TestClient(create_app(production()), base_url="https://repopilot.example.com") as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").status_code == 200


def test_docs_are_available_in_development() -> None:
    with TestClient(create_app(Settings())) as client:
        assert client.get("/openapi.json").status_code == 200


def test_allowlist_is_lowercased_and_split() -> None:
    settings = Settings(auth_allowed_github_users=" GladwynL , Other-User ,")

    assert settings.auth_allowed_github_users == ["gladwynl", "other-user"]
