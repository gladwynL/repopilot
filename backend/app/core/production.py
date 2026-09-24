"""Fail-fast configuration checks run at startup.

This runs outside Pydantic validation on purpose: Pydantic validation errors echo input values,
which here would include secrets. These messages only ever name settings.
"""

from app.core.config import Settings

MIN_SESSION_SECRET_LENGTH = 32
# Credentials from the local-development defaults must never reach production.
DEV_DATABASE_CREDENTIALS = "repopilot:repopilot@"


class ConfigurationError(Exception):
    """Invalid configuration. The message lists setting names, never values."""


def _auth_problems(settings: Settings) -> list[str]:
    problems = []
    if not settings.github_oauth_client_id:
        problems.append("GITHUB_OAUTH_CLIENT_ID is required")
    if settings.github_oauth_client_secret is None:
        problems.append("GITHUB_OAUTH_CLIENT_SECRET is required")
    if not settings.auth_allowed_github_users:
        problems.append("AUTH_ALLOWED_GITHUB_USERS must list at least one GitHub login")
    secret = settings.session_secret.get_secret_value() if settings.session_secret else ""
    if len(secret) < MIN_SESSION_SECRET_LENGTH:
        problems.append(f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters")
    if not settings.public_app_url:
        problems.append("PUBLIC_APP_URL is required for the OAuth callback")
    return problems


def configuration_problems(settings: Settings) -> list[str]:
    """Problems with the configuration (setting names only); empty when valid.

    Development and test stay convenient: only an enabled-but-incomplete auth setup is an error.
    Production additionally requires auth, HTTPS, an OpenAI key, and a non-default database.
    """
    problems = _auth_problems(settings) if settings.auth_enabled else []
    if "*" in settings.cors_origins:
        problems.append("CORS_ORIGINS must list explicit origins, not *, because cookies are used")
    if not settings.is_production:
        return problems

    if not settings.auth_enabled:
        problems.append("AUTH_ENABLED must be true in production")
    if settings.public_app_url and not settings.public_app_url.startswith("https://"):
        problems.append("PUBLIC_APP_URL must use https:// in production")
    if settings.openai_api_key is None:
        problems.append("OPENAI_API_KEY is required")
    if DEV_DATABASE_CREDENTIALS in settings.database_url or "@localhost" in settings.database_url:
        problems.append("DATABASE_URL must use the production database and its own credentials")
    return problems


def validate_settings(settings: Settings) -> None:
    problems = configuration_problems(settings)
    if problems:
        raise ConfigurationError("Invalid configuration: " + "; ".join(problems) + ".")
