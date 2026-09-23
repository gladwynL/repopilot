from collections.abc import Callable, Iterator

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_github_client
from app.core.config import Settings
from app.main import create_app
from app.services.github import GitHubClient, create_http_client
from tests.github_payloads import raw_file, raw_pull_request

URL = "/api/github/repos/octo-org/widgets/pulls/42"
Handler = Callable[[httpx.Request], httpx.Response]
ApiFactory = Callable[[Handler], TestClient]


@pytest.fixture
def api() -> Iterator[ApiFactory]:
    """Yields a factory that returns a test client whose GitHub traffic goes to ``handler``."""
    app = create_app()

    with TestClient(app) as test_client:

        def with_github(handler: Handler) -> TestClient:
            settings = Settings(github_token="sentinel-test-token")
            http = create_http_client(settings, transport=httpx.MockTransport(handler))
            app.dependency_overrides[get_github_client] = lambda: GitHubClient(http)
            return test_client

        yield with_github


def test_get_pull_request_returns_normalized_payload(api: ApiFactory) -> None:
    no_patch = raw_file("logo.png", status="added")
    del no_patch["patch"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            return httpx.Response(200, json=[raw_file(), no_patch])
        return httpx.Response(200, json=raw_pull_request())

    response = api(handler).get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["number"] == 42
    assert body["metadata"]["base"] == {
        "ref": "main",
        "sha": "a" * 40,
        "repo_full_name": "octo-org/widgets",
    }
    assert [f["filename"] for f in body["files"]] == ["src/fetcher.py", "logo.png"]
    assert body["files"][1]["patch"] is None
    assert "labels" not in body["metadata"]
    assert "blob_url" not in body["files"][0]


@pytest.mark.parametrize(
    ("upstream", "status", "detail"),
    [
        (httpx.Response(404), 404, "Repository or pull request not found on GitHub."),
        (httpx.Response(401), 502, "GitHub rejected the request credentials or permissions."),
        (httpx.Response(502), 502, "GitHub is unavailable or did not respond."),
    ],
)
def test_upstream_errors_map_to_api_errors(
    api: ApiFactory, upstream: httpx.Response, status: int, detail: str
) -> None:
    response = api(lambda _: upstream).get(URL)

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "sentinel-test-token" not in response.text


def test_rate_limit_returns_429_with_retry_after(api: ApiFactory) -> None:
    response = api(lambda _: httpx.Response(429, headers={"retry-after": "30"})).get(URL)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


@pytest.mark.parametrize(
    "path",
    [
        "/api/github/repos/octo-org/widgets/pulls/0",
        "/api/github/repos/octo-org/widgets/pulls/abc",
        "/api/github/repos/-bad-/widgets/pulls/1",
        "/api/github/repos/octo_org/widgets/pulls/1",
        "/api/github/repos/octo-org/../pulls/1",
        "/api/github/repos/octo-org/%2E%2E/pulls/1",
    ],
)
def test_invalid_path_parameters_never_reach_github(api: ApiFactory, path: str) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    response = api(handler).get(path)

    assert response.status_code in (404, 422)
    assert calls == []
