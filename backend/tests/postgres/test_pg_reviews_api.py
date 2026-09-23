"""End-to-end review API against real PostgreSQL (mocked GitHub and OpenAI HTTP)."""

from collections.abc import Iterator

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_github_client
from app.core.config import Settings
from app.main import create_app
from app.models.review import ReviewFindingRecord, ReviewRecord
from app.services.github import GitHubClient, create_http_client
from tests.github_payloads import raw_file, raw_pull_request
from tests.review_helpers import responses_api_body, review_json

BODY = {"owner": "octo-org", "repo": "widgets", "pull_number": 42}
FINDING = {
    "category": "bug",
    "severity": "high",
    "confidence": 0.9,
    "title": "Broken",
    "description": "d",
    "suggestion": "s",
    "file": "src/fetcher.py",
    "line_start": 2,
    "line_end": None,
}


class Api:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.head_sha = "b" * 40
        self.openai_calls = 0
        app = client.app

        def github(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/files"):
                return httpx.Response(200, json=[raw_file()])
            pr = raw_pull_request()
            pr["head"]["sha"] = self.head_sha
            return httpx.Response(200, json=pr)

        def openai(_: httpx.Request) -> httpx.Response:
            self.openai_calls += 1
            return httpx.Response(200, json=responses_api_body(review_json(findings=[FINDING])))

        http = create_http_client(Settings(), transport=httpx.MockTransport(github))
        app.dependency_overrides[get_github_client] = lambda: GitHubClient(http)
        app.state.openai_client = AsyncOpenAI(
            api_key="sk-test-sentinel-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(openai)),
        )

    def review(self, force: bool = False) -> httpx.Response:
        return self.client.post(
            "/api/reviews/github", json=BODY, params={"force": str(force).lower()}
        )


@pytest.fixture
def api(pg_url: str, session_factory: sessionmaker[Session]) -> Iterator[Api]:
    settings = Settings(database_url=pg_url, openai_api_key="sk-test-sentinel-key")
    with TestClient(create_app(settings)) as client:
        yield Api(client)


def test_review_is_persisted_then_served_from_cache(
    api: Api, session_factory: sessionmaker[Session]
) -> None:
    first = api.review()
    second = api.review()

    assert first.status_code == second.status_code == 200
    assert (first.json()["cached"], second.json()["cached"]) == (False, True)
    assert second.json()["id"] == first.json()["id"]
    assert api.openai_calls == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReviewRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ReviewFindingRecord)) == 1


def test_new_head_sha_and_force_create_new_reviews(api: Api) -> None:
    first = api.review().json()
    api.head_sha = "c" * 40
    second = api.review().json()
    forced = api.review(force=True).json()

    assert not second["cached"] and not forced["cached"]
    assert len({first["id"], second["id"], forced["id"]}) == 3
    assert api.openai_calls == 3

    history = api.client.get("/api/reviews", params={"owner": "octo-org"}).json()
    assert history["total"] == 3
    assert history["items"][0]["id"] == forced["id"]
    by_id = {item["id"]: item for item in history["items"]}
    assert by_id[second["id"]]["is_current"] is False
    assert by_id[forced["id"]]["finding_count"] == 1


def test_get_review_by_id_from_database(api: Api) -> None:
    created = api.review().json()

    fetched = api.client.get(f"/api/reviews/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["review"] == created["review"]
    assert api.openai_calls == 1


def test_ready_reports_database_available(api: Api) -> None:
    response = api.client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
