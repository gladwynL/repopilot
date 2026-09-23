from collections.abc import Callable
from datetime import UTC, datetime

import httpx2 as httpx
import pytest

from app.core.config import Settings
from app.services.github import (
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubResponseError,
    GitHubUnavailableError,
    build_headers,
    create_http_client,
    normalize_file,
    normalize_metadata,
)
from tests.github_payloads import raw_file, raw_pull_request

PR_PATH = "/repos/octo-org/widgets/pulls/42"
Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, token: str | None = None) -> GitHubClient:
    settings = Settings(github_token=token)
    return GitHubClient(create_http_client(settings, transport=httpx.MockTransport(handler)))


def respond_with(response: httpx.Response) -> Handler:
    return lambda _: response


# --- headers ---------------------------------------------------------------


def test_headers_without_token_omit_authorization() -> None:
    headers = build_headers(None, "2026-03-10")

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2026-03-10"
    assert "Authorization" not in headers


def test_headers_with_token_use_bearer_auth() -> None:
    assert build_headers("tok123", "2026-03-10")["Authorization"] == "Bearer tok123"


def test_blank_token_setting_is_treated_as_missing() -> None:
    assert Settings(github_token="  ").github_token is None


def test_token_is_hidden_from_settings_repr() -> None:
    assert "sentinel-test-token" not in repr(Settings(github_token="sentinel-test-token"))


@pytest.mark.anyio
async def test_requests_carry_configured_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = raw_pull_request() if request.url.path == PR_PATH else []
        return httpx.Response(200, json=body)

    await make_client(handler, token="tok123").get_pull_request("octo-org", "widgets", 42)

    assert [r.url.path for r in seen] == [PR_PATH, f"{PR_PATH}/files"]
    for request in seen:
        assert request.url.host == "api.github.com"
        assert request.headers["Authorization"] == "Bearer tok123"
        assert request.headers["X-GitHub-Api-Version"] == "2026-03-10"


# --- normalization ---------------------------------------------------------


def test_normalize_metadata() -> None:
    metadata = normalize_metadata(raw_pull_request())

    assert metadata.owner == "octo-org"
    assert metadata.repo == "widgets"
    assert metadata.number == 42
    assert metadata.title == "Add retry logic to fetcher"
    assert metadata.state == "open"
    assert metadata.draft is False
    assert metadata.author_login == "octocat"
    assert metadata.base.ref == "main"
    assert metadata.base.sha == "a" * 40
    assert metadata.head.ref == "feature/retry"
    assert metadata.head.repo_full_name == "contrib/widgets"
    assert metadata.created_at == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    assert (metadata.additions, metadata.deletions) == (30, 5)
    assert (metadata.changed_files, metadata.commits) == (2, 3)


def test_normalize_metadata_tolerates_deleted_author_and_fork() -> None:
    raw = raw_pull_request(user=None, body=None)
    raw["head"]["repo"] = None

    metadata = normalize_metadata(raw)

    assert metadata.author_login is None
    assert metadata.body is None
    assert metadata.head.repo_full_name is None


def test_normalize_file() -> None:
    file = normalize_file(raw_file())

    assert file.filename == "src/fetcher.py"
    assert file.status == "modified"
    assert (file.additions, file.deletions, file.changes) == (10, 2, 12)
    assert file.sha == "c" * 40
    assert file.patch == "@@ -1,2 +1,10 @@\n-old\n+new"
    assert file.previous_filename is None


def test_normalize_file_without_patch() -> None:
    raw = raw_file("assets/logo.png", status="added")
    del raw["patch"]

    assert normalize_file(raw).patch is None


def test_normalize_renamed_file() -> None:
    raw = raw_file("src/new.py", status="renamed", previous_filename="src/old.py")

    assert normalize_file(raw).previous_filename == "src/old.py"


# --- fetching --------------------------------------------------------------


@pytest.mark.anyio
async def test_get_pull_request_follows_file_pagination() -> None:
    files_url = f"https://api.github.com{PR_PATH}/files"
    pages = {
        None: (
            [raw_file("a.py"), raw_file("b.py")],
            f'<{files_url}?per_page=100&page=2>; rel="next"',
        ),
        "2": ([raw_file("c.py")], None),
    }
    file_requests: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PR_PATH:
            return httpx.Response(200, json=raw_pull_request())
        file_requests.append(request.url)
        body, link = pages[request.url.params.get("page")]
        return httpx.Response(200, json=body, headers={"Link": link} if link else {})

    pr = await make_client(handler).get_pull_request("octo-org", "widgets", 42)

    assert [f.filename for f in pr.files] == ["a.py", "b.py", "c.py"]
    assert [url.params.get("per_page") for url in file_requests] == ["100", "100"]


@pytest.mark.anyio
async def test_pagination_refuses_links_to_other_hosts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PR_PATH:
            return httpx.Response(200, json=raw_pull_request())
        link = '<https://evil.test/steal>; rel="next"'
        return httpx.Response(200, json=[raw_file()], headers={"Link": link})

    with pytest.raises(GitHubResponseError):
        await make_client(handler).get_pull_request("octo-org", "widgets", 42)


# --- errors ----------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(404, json={"message": "Not Found"}), GitHubNotFoundError),
        (httpx.Response(401, json={"message": "Bad credentials"}), GitHubAuthError),
        (httpx.Response(403, json={"message": "Resource not accessible"}), GitHubAuthError),
        (httpx.Response(500), GitHubUnavailableError),
        (httpx.Response(503), GitHubUnavailableError),
        (httpx.Response(422, json={"message": "Validation Failed"}), GitHubResponseError),
    ],
)
async def test_upstream_status_maps_to_internal_error(
    response: httpx.Response, expected: type[Exception]
) -> None:
    with pytest.raises(expected):
        await make_client(respond_with(response)).get_pull_request("octo-org", "widgets", 42)


@pytest.mark.anyio
async def test_primary_rate_limit_reports_seconds_until_reset() -> None:
    reset = int(datetime.now(UTC).timestamp()) + 120
    response = httpx.Response(
        403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}
    )

    with pytest.raises(GitHubRateLimitError) as exc_info:
        await make_client(respond_with(response)).get_pull_request("octo-org", "widgets", 42)

    assert exc_info.value.retry_after is not None
    assert 110 <= exc_info.value.retry_after <= 120


@pytest.mark.anyio
async def test_secondary_rate_limit_uses_retry_after_header() -> None:
    response = httpx.Response(429, headers={"retry-after": "60"})

    with pytest.raises(GitHubRateLimitError) as exc_info:
        await make_client(respond_with(response)).get_pull_request("octo-org", "widgets", 42)

    assert exc_info.value.retry_after == 60


@pytest.mark.anyio
async def test_network_failure_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(GitHubUnavailableError):
        await make_client(handler).get_pull_request("octo-org", "widgets", 42)


@pytest.mark.anyio
async def test_malformed_payload_maps_to_response_error() -> None:
    broken = raw_pull_request()
    del broken["head"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=broken if request.url.path == PR_PATH else [])

    with pytest.raises(GitHubResponseError):
        await make_client(handler).get_pull_request("octo-org", "widgets", 42)
