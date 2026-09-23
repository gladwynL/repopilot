from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.reviews import ReviewRepository
from app.services.ai.base import AIConfigurationError
from app.services.ai.config import ReviewConfig
from app.services.ai.factory import create_review_engine
from app.services.ai.review_engine import ReviewEngine
from app.services.github import GitHubClient
from app.services.reviews import ReviewService


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


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


def get_review_service(
    github: Annotated[GitHubClient, Depends(get_github_client)],
    repository: Annotated[ReviewRepository, Depends(get_review_repository)],
    config: Annotated[ReviewConfig, Depends(get_review_config)],
    engine_factory: Annotated[Callable[[], ReviewEngine], Depends(get_review_engine_factory)],
) -> ReviewService:
    return ReviewService(github, repository, config, engine_factory)
