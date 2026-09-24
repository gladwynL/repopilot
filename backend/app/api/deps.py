import asyncio
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.reviews import ReviewRepository
from app.services.ai.base import AIConfigurationError
from app.services.ai.config import ReviewConfig
from app.services.ai.factory import create_review_engine
from app.services.ai.review_engine import ReviewEngine
from app.services.auth import SESSION_USER_KEY, GitHubOAuthClient, SessionUser, is_allowed
from app.services.github import GitHubClient
from app.services.reviews import ReviewService


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


# --- authentication ----------------------------------------------------------------------


def get_current_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings_from_app)]
) -> SessionUser | None:
    """The signed-in user, or None. Always None when auth is disabled.

    The allowlist is re-checked on every request, so removing a login takes effect without
    waiting for existing sessions to expire.
    """
    if not settings.auth_enabled:
        return None
    data = request.session.get(SESSION_USER_KEY)
    if not isinstance(data, dict):
        return None
    try:
        user = SessionUser.model_validate(data)
    except ValueError:
        request.session.clear()
        return None
    if not is_allowed(settings, user.login):
        request.session.clear()
        return None
    return user


def require_user(
    settings: Annotated[Settings, Depends(get_settings_from_app)],
    user: Annotated[SessionUser | None, Depends(get_current_user)],
) -> SessionUser | None:
    """Gate for application endpoints. A no-op when auth is disabled (local development)."""
    if settings.auth_enabled and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to use RepoPilot."
        )
    return user


def get_oauth_client(request: Request) -> GitHubOAuthClient:
    return GitHubOAuthClient(request.app.state.oauth_http, request.app.state.settings)


# --- services ------------------------------------------------------------------------------


def get_github_client(request: Request) -> GitHubClient:
    return GitHubClient(request.app.state.github_http)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_review_repository(session: Annotated[Session, Depends(get_db)]) -> ReviewRepository:
    return ReviewRepository(session)


def get_review_config(
    settings: Annotated[Settings, Depends(get_settings_from_app)],
) -> ReviewConfig:
    return ReviewConfig.from_settings(settings)


def get_review_engine_factory(request: Request) -> Callable[[], ReviewEngine]:
    def create() -> ReviewEngine:
        client = request.app.state.openai_client
        if client is None:
            raise AIConfigurationError("AI review is not configured on this server.")
        return create_review_engine(request.app.state.settings, client)

    return create


def get_review_slots(request: Request) -> asyncio.Semaphore:
    return request.app.state.review_slots


def get_review_service(
    github: Annotated[GitHubClient, Depends(get_github_client)],
    repository: Annotated[ReviewRepository, Depends(get_review_repository)],
    config: Annotated[ReviewConfig, Depends(get_review_config)],
    engine_factory: Annotated[Callable[[], ReviewEngine], Depends(get_review_engine_factory)],
    slots: Annotated[asyncio.Semaphore, Depends(get_review_slots)],
) -> ReviewService:
    return ReviewService(github, repository, config, engine_factory, review_slots=slots)
