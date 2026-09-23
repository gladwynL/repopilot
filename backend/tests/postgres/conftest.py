"""Fixtures for tests that need a real PostgreSQL database.

Set TEST_DATABASE_URL to a disposable database whose name ends in ``_test``, e.g. the
Compose ``test-db`` service:

    docker compose --profile test up -d --wait test-db
    TEST_DATABASE_URL=postgresql+psycopg://repopilot:repopilot@localhost:55432/repopilot_test

The schema is rebuilt from the Alembic migrations once per session and every table is
truncated before each test. Without TEST_DATABASE_URL these tests are skipped.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import create_db_engine, create_session_factory
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(str(item.fspath)).parent == Path(__file__).parent:
            item.add_marker(pytest.mark.postgres)


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.fail(f"Refusing to use database {database!r}: its name must end in '_test'.")
    return url


@pytest.fixture(scope="session")
def pg_engine(pg_url: str) -> Iterator[Engine]:
    config = alembic_config(pg_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_db_engine(pg_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with pg_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return create_session_factory(pg_engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s
