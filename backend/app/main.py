import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.core.production import validate_settings
from app.db.session import create_db_engine, create_session_factory
from app.services.ai.openai_provider import create_openai_client
from app.services.auth import create_oauth_http_client
from app.services.github import create_http_client

SESSION_COOKIE_NAME = "repopilot_session"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    # Fail fast on unsafe or incomplete configuration (messages name settings, never values).
    validate_settings(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db_engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(app.state.db_engine)
        app.state.openai_client = create_openai_client(settings)
        app.state.review_slots = asyncio.Semaphore(settings.review_max_concurrent)
        try:
            async with (
                create_http_client(settings) as github_http,
                create_oauth_http_client() as oauth_http,
            ):
                app.state.github_http = github_http
                app.state.oauth_http = oauth_http
                yield
        finally:
            if app.state.openai_client is not None:
                await app.state.openai_client.close()
            app.state.db_engine.dispose()

    # Interactive docs describe private endpoints, so they are off in production.
    docs = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    if settings.auth_enabled and settings.session_secret is not None:
        # Signed (not encrypted) cookie: holds only the public GitHub identity and the
        # short-lived OAuth state/PKCE verifier. Lax keeps it off cross-site POSTs.
        app.add_middleware(
            SessionMiddleware,
            secret_key=settings.session_secret.get_secret_value(),
            session_cookie=SESSION_COOKIE_NAME,
            max_age=settings.session_max_age_seconds,
            same_site="lax",
            https_only=settings.secure_cookies,
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
