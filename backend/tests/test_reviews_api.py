"""End-to-end review endpoint tests: real app wiring, mocked GitHub and OpenAI HTTP."""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.api.deps import get_github_client
from app.core.config import Settings
from app.main import create_app
from app.services.github import GitHubClient, create_http_client
from tests.github_payloads import raw_file, raw_pull_request
from tests.review_helpers import responses_api_body, review_json

URL = "/api/reviews/github"
BODY = {"owner": "octo-org", "repo": "widgets", "pull_number": 42}
OPENAI_KEY = "sk-test-sentinel-key"
GITHUB_TOKEN = "sentinel-github-token"
SECRET_PATCH_LINE = "SECRET_PATCH_CONTENT"

Handler = Callable[[httpx.Request], httpx.Response]


def github_ok(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/files"):
        patch = f"@@ -1,2 +1,2 @@\n import os\n-a = 1\n+a = '{SECRET_PATCH_LINE}'"
        return httpx.Response(200, json=[raw_file("src/app.py", patch=patch)])
    return httpx.Response(200, json=raw_pull_request())


def openai_ok(output: str | None = None) -> Handler:
    return lambda _: httpx.Response(200, json=responses_api_body(output or review_json()))


@dataclass
class Harness:
    client: TestClient
    openai_requests: list[httpx.Request] = field(default_factory=list)

    def post(
        self, body: object = BODY, *, github: Handler = github_ok, openai: Handler
    ) -> httpx.Response:
        app = self.client.app
        github_http = create_http_client(
            Settings(github_token=GITHUB_TOKEN), transport=httpx.MockTransport(github)
        )
        app.dependency_overrides[get_github_client] = lambda: GitHubClient(github_http)

        def recording(request: httpx.Request) -> httpx.Response:
            self.openai_requests.append(request)
            return openai(request)

        app.state.openai_client = AsyncOpenAI(
            api_key=OPENAI_KEY,
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(recording)),
        )
        return self.client.post(URL, json=body)


@pytest.fixture
def harness() -> Iterator[Harness]:
    settings = Settings(openai_api_key=OPENAI_KEY, openai_max_retries=0)
    with TestClient(create_app(settings)) as client:
        yield Harness(client)


def assert_no_secrets(response: httpx.Response) -> None:
    for secret in (OPENAI_KEY, GITHUB_TOKEN, SECRET_PATCH_LINE, "Bearer"):
        assert secret not in response.text


def test_successful_review(harness: Harness) -> None:
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
    assert body["pull_request"] == {
        "owner": "octo-org",
        "repo": "widgets",
        "number": 42,
        "head_sha": "b" * 40,
    }
    assert body["model"] == "gpt-5.6-terra"
    assert body["risk_level"] == "medium"
    assert body["reviewed_files"] == ["src/app.py"]
    assert body["findings"][0]["line_start"] == 2
    assert body["findings"][0]["file"] == "src/app.py"
    (openai_request,) = harness.openai_requests
    sent = json.loads(openai_request.content)
    assert SECRET_PATCH_LINE in sent["input"]  # the diff reaches the model...
    assert GITHUB_TOKEN not in sent["input"]  # ...but credentials never do
    assert OPENAI_KEY not in sent["input"]


def test_github_failure_preserves_phase_1_behavior(harness: Harness) -> None:
    response = harness.post(github=lambda _: httpx.Response(404), openai=openai_ok())

    assert response.status_code == 404
    assert response.json() == {"detail": "Repository or pull request not found on GitHub."}
    assert harness.openai_requests == []


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
def test_ai_failures_map_to_api_errors(
    harness: Harness, openai: Handler, status: int, detail: str
) -> None:
    response = harness.post(openai=openai)

    assert response.status_code == status
    assert response.json() == {"detail": detail}
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
    github_calls: list[httpx.Request] = []

    def github(request: httpx.Request) -> httpx.Response:
        github_calls.append(request)
        return github_ok(request)

    response = harness.post(body, github=github, openai=openai_ok())

    assert response.status_code == 422
    assert github_calls == []
    assert harness.openai_requests == []


def test_missing_api_key_returns_503_without_calling_github() -> None:
    github_calls: list[httpx.Request] = []

    def github(request: httpx.Request) -> httpx.Response:
        github_calls.append(request)
        return github_ok(request)

    app = create_app(Settings(openai_api_key=None))
    http = create_http_client(Settings(), transport=httpx.MockTransport(github))
    app.dependency_overrides[get_github_client] = lambda: GitHubClient(http)
    with TestClient(app) as client:
        response = client.post(URL, json=BODY)

    assert response.status_code == 503
    assert response.json() == {"detail": "AI review is not configured on this server."}
    assert github_calls == []
