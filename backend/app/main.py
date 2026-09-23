from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.db.session import create_db_engine, create_session_factory
from app.services.ai.openai_provider import create_openai_client
from app.services.github import create_http_client


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db_engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(app.state.db_engine)
        app.state.openai_client = create_openai_client(settings)
        try:
            async with create_http_client(settings) as github_http:
                app.state.github_http = github_http
                yield
        finally:
            if app.state.openai_client is not None:
                await app.state.openai_client.close()
            app.state.db_engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
