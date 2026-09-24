"""Review API tests: real app wiring and dependencies, mocked GitHub/OpenAI HTTP, and an
in-memory review store. The same flows run against PostgreSQL in tests/postgres/."""

import asyncio
import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.api.deps import get_github_client, get_review_repository
from app.core.config import Settings
from app.db.errors import PersistenceError
from app.main import create_app
from app.services.ai.config import ReviewConfig, review_cache_key
from app.services.github import GitHubClient, create_http_client
from tests.github_payloads import raw_file, raw_pull_request
from tests.review_helpers import (
    InMemoryReviewStore,
    responses_api_body,
    review_json,
    review_result,
)

URL = "/api/reviews/github"
BODY = {"owner": "octo-org", "repo": "widgets", "pull_number": 42}
OPENAI_KEY = "sk-test-sentinel-key"
GITHUB_TOKEN = "sentinel-github-token"
SECRET_PATCH_LINE = "SECRET_PATCH_CONTENT"

Handler = Callable[[httpx.Request], httpx.Response]


def github_pr(head_sha: str = "b" * 40) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            patch = f"@@ -1,2 +1,2 @@\n import os\n-a = 1\n+a = '{SECRET_PATCH_LINE}'"
            return httpx.Response(200, json=[raw_file("src/app.py", patch=patch)])
        pr = raw_pull_request()
        pr["head"]["sha"] = head_sha
        return httpx.Response(200, json=pr)

    return handler


def openai_ok(output: str | None = None) -> Handler:
    return lambda _: httpx.Response(200, json=responses_api_body(output or review_json()))


@dataclass
class Harness:
    client: TestClient
    store: InMemoryReviewStore = field(default_factory=InMemoryReviewStore)
    openai_requests: list[httpx.Request] = field(default_factory=list)
    github_requests: list[httpx.Request] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.client.app.dependency_overrides[get_review_repository] = lambda: self.store

    def post(
        self,
        body: object = BODY,
        *,
        github: Handler | None = None,
        openai: Handler | None = None,
        force: bool | None = None,
    ) -> httpx.Response:
        app = self.client.app
        github = github or github_pr()
        openai = openai or openai_ok()

        def record_github(request: httpx.Request) -> httpx.Response:
            self.github_requests.append(request)
            return github(request)

        github_http = create_http_client(
            Settings(github_token=GITHUB_TOKEN), transport=httpx.MockTransport(record_github)
        )
        app.dependency_overrides[get_github_client] = lambda: GitHubClient(github_http)

        def record_openai(request: httpx.Request) -> httpx.Response:
            self.openai_requests.append(request)
            return openai(request)

        if app.state.openai_client is not None:
            app.state.openai_client = AsyncOpenAI(
                api_key=OPENAI_KEY,
                max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(record_openai)),
            )
        params = {"force": str(force).lower()} if force is not None else None
        return self.client.post(URL, json=body, params=params)


def make_harness(settings: Settings) -> Iterator[Harness]:
    with TestClient(create_app(settings)) as client:
        yield Harness(client)


@pytest.fixture
def harness() -> Iterator[Harness]:
    yield from make_harness(Settings(openai_api_key=OPENAI_KEY, openai_max_retries=0))


@pytest.fixture
def keyless_harness() -> Iterator[Harness]:
    yield from make_harness(Settings(openai_api_key=None))


def assert_no_secrets(response: httpx.Response) -> None:
    for secret in (OPENAI_KEY, GITHUB_TOKEN, SECRET_PATCH_LINE, "Bearer", "postgresql"):
        assert secret not in response.text


# --- review + cache ------------------------------------------------------------------


def test_first_review_runs_model_and_persists(harness: Harness) -> None:
    output = review_json(
        risk_level="medium",
        findings=[
            {
                "category": "bug",
                "severity": "medium",
                "confidence": 0.85,
                "title": "Type changed from int to str",
                "description": "Callers doing arithmetic on `a` will break.",
                "suggestion": "Keep `a` numeric or update callers.",
                "file": "src/app.py",
                "line_start": 2,
                "line_end": None,
            }
        ],
    )

    response = harness.post(openai=openai_ok(output))

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert body["is_current"] is True
    uuid.UUID(body["id"])
    review = body["review"]
    assert review["pull_request"]["head_sha"] == "b" * 40
    assert review["model"] == "gpt-5.6-terra"
    assert review["findings"][0]["line_start"] == 2
    assert len(harness.store.rows) == 1
    (openai_request,) = harness.openai_requests
    sent = json.loads(openai_request.content)
    assert SECRET_PATCH_LINE in sent["input"]
    assert GITHUB_TOKEN not in sent["input"]
    assert OPENAI_KEY not in sent["input"]


def test_unchanged_pr_is_served_from_cache_without_model_call(harness: Harness) -> None:
    first = harness.post().json()

    second = harness.post()

    assert second.status_code == 200
    body = second.json()
    assert body["cached"] is True
    assert body["id"] == first["id"]
    assert body["review"] == first["review"]
    assert len(harness.openai_requests) == 1
    assert len(harness.github_requests) == 4  # the PR is still re-fetched to learn head_sha


def test_new_commit_misses_cache(harness: Harness) -> None:
    first = harness.post(github=github_pr("b" * 40)).json()

    second = harness.post(github=github_pr("c" * 40)).json()

    assert second["cached"] is False
    assert second["id"] != first["id"]
    assert len(harness.openai_requests) == 2


def test_force_rerun_creates_new_current_review(harness: Harness) -> None:
    first = harness.post().json()

    forced = harness.post(force=True)

    assert forced.status_code == 200
    body = forced.json()
    assert body["cached"] is False
    assert body["id"] != first["id"]
    assert len(harness.openai_requests) == 2
    old = harness.client.get(f"/api/reviews/{first['id']}").json()
    assert old["is_current"] is False
    assert harness.post().json()["id"] == body["id"]  # cache now returns the re-run


def test_cached_review_served_without_ai_configuration(keyless_harness: Harness) -> None:
    config = ReviewConfig.from_settings(Settings(openai_api_key=None))
    seeded = keyless_harness.store.save(
        review_result(),
        cache_key=review_cache_key(
            config, owner="octo-org", repo="widgets", pull_number=42, head_sha="b" * 40
        ),
        review_config=config.model_dump(),
        provider="openai",
        replace_current=False,
    )

    response = keyless_harness.post()

    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert response.json()["id"] == str(seeded.id)


def test_missing_api_key_returns_503_on_cache_miss(keyless_harness: Harness) -> None:
    response = keyless_harness.post()

    assert response.status_code == 503
    assert response.json() == {"detail": "AI review is not configured on this server."}
    assert keyless_harness.store.rows == []


# --- upstream failures ----------------------------------------------------------------


def test_github_failure_preserves_phase_1_behavior(harness: Harness) -> None:
    response = harness.post(github=lambda _: httpx.Response(404))

    assert response.status_code == 404
    assert response.json() == {"detail": "Repository or pull request not found on GitHub."}
    assert harness.openai_requests == []
    assert harness.store.rows == []


def error(status: int, code: str | None = None, **headers: str) -> Handler:
    body = {"error": {"message": f"upstream detail {OPENAI_KEY}", "type": "x", "code": code}}
    return lambda _: httpx.Response(status, json=body, headers=headers)


@pytest.mark.parametrize(
    ("openai", "status", "detail"),
    [
        (error(401), 503, "The AI provider rejected the configured credentials."),
        (error(429, "insufficient_quota"), 503, "The AI provider account has no remaining quota."),
        (error(429), 503, "The AI provider is rate limiting requests. Try again later."),
        (error(500), 502, "The AI provider is unavailable."),
        (openai_ok("{not json"), 502, "The AI provider returned an invalid review."),
    ],
)
def test_ai_failures_map_to_api_errors_and_store_nothing(
    harness: Harness, openai: Handler, status: int, detail: str
) -> None:
    response = harness.post(openai=openai)

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert harness.store.rows == []
    assert_no_secrets(response)


def test_ai_rate_limit_passes_retry_after(harness: Harness) -> None:
    response = harness.post(openai=error(429, **{"retry-after": "45"}))

    assert response.status_code == 503
    assert response.headers["retry-after"] == "45"


def test_ai_timeout_maps_to_504(harness: Harness) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    response = harness.post(openai=timeout)

    assert response.status_code == 504
    assert_no_secrets(response)


def test_database_failure_on_lookup_returns_503_before_model_call(harness: Harness) -> None:
    harness.store.fail_with = PersistenceError()

    response = harness.post()

    assert response.status_code == 503
    assert response.json() == {"detail": "Review storage is unavailable."}
    assert harness.openai_requests == []


def test_database_failure_on_save_does_not_repeat_model_call(harness: Harness) -> None:
    original_save = harness.store.save

    def failing_save(*args: object, **kwargs: object) -> None:
        raise PersistenceError()

    harness.store.save = failing_save  # type: ignore[method-assign]
    response = harness.post()
    harness.store.save = original_save  # type: ignore[method-assign]

    assert response.status_code == 503
    assert len(harness.openai_requests) == 1
    assert_no_secrets(response)


# --- validation -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"owner": "octo-org", "repo": "widgets", "pull_number": 0},
        {"owner": "octo_org", "repo": "widgets", "pull_number": 1},
        {"owner": "octo-org", "repo": "..", "pull_number": 1},
        {"owner": "octo-org", "repo": "widgets"},
        {"owner": "https://evil.test", "repo": "widgets", "pull_number": 1},
        "not an object",
    ],
)
def test_invalid_input_rejected_before_any_upstream_call(harness: Harness, body: object) -> None:
    response = harness.post(body)

    assert response.status_code == 422
    assert harness.github_requests == []
    assert harness.openai_requests == []


def test_invalid_force_value_rejected(harness: Harness) -> None:
    response = harness.client.post(URL, json=BODY, params={"force": "maybe"})

    assert response.status_code == 422


# --- history and lookup ---------------------------------------------------------------


def test_get_review_by_id(harness: Harness) -> None:
    created = harness.post().json()
    github_calls = len(harness.github_requests)

    response = harness.client.get(f"/api/reviews/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["review"] == created["review"]
    assert "cached" not in body
    assert len(harness.github_requests) == github_calls
    assert len(harness.openai_requests) == 1


def test_unknown_review_id_is_404(harness: Harness) -> None:
    response = harness.client.get(f"/api/reviews/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Review not found."}


def test_malformed_review_id_is_422(harness: Harness) -> None:
    assert harness.client.get("/api/reviews/not-a-uuid").status_code == 422


def test_history_lists_newest_first_with_filters(harness: Harness) -> None:
    harness.post(github=github_pr("1" * 40))
    harness.post(github=github_pr("2" * 40))

    response = harness.client.get("/api/reviews", params={"owner": "OCTO-ORG", "pull_number": 42})

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert [item["head_sha"] for item in page["items"]] == ["2" * 40, "1" * 40]
    assert set(page["items"][0]) >= {
        "id",
        "owner",
        "repo",
        "pull_number",
        "risk_level",
        "finding_count",
        "model",
        "prompt_version",
        "created_at",
    }
    assert harness.client.get("/api/reviews", params={"repo": "other"}).json()["total"] == 0


def test_history_pagination(harness: Harness) -> None:
    for sha in ("1", "2", "3"):
        harness.post(github=github_pr(sha * 40))

    page = harness.client.get("/api/reviews", params={"limit": 2, "offset": 2}).json()

    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 2)
    assert [item["head_sha"] for item in page["items"]] == ["1" * 40]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"pull_number": 0}, {"owner": "bad_owner"}],
)
def test_history_rejects_invalid_parameters(harness: Harness, params: dict[str, object]) -> None:
    assert harness.client.get("/api/reviews", params=params).status_code == 422


def test_history_database_failure_is_503(harness: Harness) -> None:
    harness.store.fail_with = PersistenceError()

    response = harness.client.get("/api/reviews")

    assert response.status_code == 503
    assert response.json() == {"detail": "Review storage is unavailable."}


def test_review_capacity_limit_returns_429(harness: Harness) -> None:
    harness.client.app.state.review_slots = asyncio.Semaphore(0)

    response = harness.post()

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert "maximum number of AI reviews" in response.json()["detail"]
    assert harness.openai_requests == []
