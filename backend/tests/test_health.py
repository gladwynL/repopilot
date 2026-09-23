from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_is_503_when_database_unreachable() -> None:
    url = "postgresql+psycopg://nobody:secret-db-password@127.0.0.1:1/nothing"
    with TestClient(create_app(Settings(database_url=url))) as client:
        ready = client.get("/ready")
        health = client.get("/health")

    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
    assert "secret-db-password" not in ready.text
    assert health.status_code == 200  # liveness does not depend on the database
