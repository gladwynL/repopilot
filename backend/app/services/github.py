"""GitHub REST API integration: fetches pull requests and normalizes them."""

import time
from typing import Any
from urllib.parse import quote

import httpx2 as httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.pull_request import (
    GitRef,
    PullRequest,
    PullRequestFile,
    PullRequestMetadata,
)

FILES_PER_PAGE = 100
REQUEST_TIMEOUT_SECONDS = 15.0


class GitHubError(Exception):
    """Base class for failures talking to GitHub. Messages are safe to show to API clients."""

    message = "GitHub request failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class GitHubNotFoundError(GitHubError):
    message = "Repository or pull request not found on GitHub."


class GitHubAuthError(GitHubError):
    message = "GitHub rejected the request credentials or permissions."


class GitHubRateLimitError(GitHubError):
    message = "GitHub API rate limit exceeded."

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__()
        self.retry_after = retry_after


class GitHubUnavailableError(GitHubError):
    message = "GitHub is unavailable or did not respond."


class GitHubResponseError(GitHubError):
    message = "GitHub returned an unexpected response."


def build_headers(token: str | None, api_version: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": api_version,
        "User-Agent": "RepoPilot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def create_http_client(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    token = settings.github_token.get_secret_value() if settings.github_token else None
    return httpx.AsyncClient(
        base_url=settings.github_api_url,
        headers=build_headers(token, settings.github_api_version),
        timeout=REQUEST_TIMEOUT_SECONDS,
        transport=transport,
    )


class GitHubClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{number}"
        raw_pr = await self._get_json(path)
        raw_files = await self._get_paginated(f"{path}/files", params={"per_page": FILES_PER_PAGE})
        try:
            return PullRequest(
                metadata=normalize_metadata(raw_pr),
                files=[normalize_file(raw) for raw in raw_files],
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise GitHubResponseError() from exc

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request(url, params)
        return response.json()

    async def _get_paginated(self, url: str, params: dict[str, Any]) -> list[Any]:
        items: list[Any] = []
        next_url: str | None = url
        next_params: dict[str, Any] | None = params
        while next_url:
            response = await self._request(next_url, next_params)
            page = response.json()
            if not isinstance(page, list):
                raise GitHubResponseError()
            items.extend(page)
            next_url = self._next_page_url(response)
            next_params = None  # the Link header URL already carries the query string
        return items

    def _next_page_url(self, response: httpx.Response) -> str | None:
        url = response.links.get("next", {}).get("url")
        if url is None:
            return None
        # Never follow a pagination link to another host: it would receive our token.
        if httpx.URL(url).host != self._http.base_url.host:
            raise GitHubResponseError()
        return url

    async def _request(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        try:
            response = await self._http.get(url, params=params)
        except httpx.RequestError as exc:
            raise GitHubUnavailableError() from exc
        _raise_for_status(response)
        return response


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    if _is_rate_limited(response):
        raise GitHubRateLimitError(retry_after=_retry_after_seconds(response))
    if status == 404:
        raise GitHubNotFoundError()
    if status in (401, 403):
        raise GitHubAuthError()
    if status >= 500:
        raise GitHubUnavailableError()
    raise GitHubResponseError()


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    headers = response.headers
    return headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers


def _retry_after_seconds(response: httpx.Response) -> int | None:
    headers = response.headers
    if (retry_after := headers.get("retry-after", "")).isdigit():
        return int(retry_after)
    if (reset := headers.get("x-ratelimit-reset", "")).isdigit():
        return max(int(reset) - int(time.time()), 0)
    return None


def normalize_metadata(raw: dict[str, Any]) -> PullRequestMetadata:
    base_repo = raw["base"]["repo"]
    return PullRequestMetadata(
        owner=base_repo["owner"]["login"],
        repo=base_repo["name"],
        number=raw["number"],
        title=raw["title"],
        body=raw.get("body"),
        state=raw["state"],
        draft=raw.get("draft", False),
        merged=raw.get("merged", False),
        author_login=(raw.get("user") or {}).get("login"),
        html_url=raw["html_url"],
        base=_normalize_ref(raw["base"]),
        head=_normalize_ref(raw["head"]),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        additions=raw["additions"],
        deletions=raw["deletions"],
        changed_files=raw["changed_files"],
        commits=raw["commits"],
    )


def _normalize_ref(raw: dict[str, Any]) -> GitRef:
    return GitRef(
        ref=raw["ref"],
        sha=raw["sha"],
        repo_full_name=(raw.get("repo") or {}).get("full_name"),
    )


def normalize_file(raw: dict[str, Any]) -> PullRequestFile:
    return PullRequestFile(
        filename=raw["filename"],
        status=raw["status"],
        additions=raw["additions"],
        deletions=raw["deletions"],
        changes=raw["changes"],
        sha=raw.get("sha"),
        patch=raw.get("patch"),
        previous_filename=raw.get("previous_filename"),
    )
