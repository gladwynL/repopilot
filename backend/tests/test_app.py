from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_app_module_imports() -> None:
    from app.main import app

    assert isinstance(app, FastAPI)


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test,")

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_allows_configured_origin() -> None:
    client = TestClient(create_app(Settings(cors_origins="http://allowed.test")))

    allowed = client.get("/health", headers={"Origin": "http://allowed.test"})
    blocked = client.get("/health", headers={"Origin": "http://blocked.test"})

    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"
    assert "access-control-allow-origin" not in blocked.headers
