"""Trimmed GitHub REST payloads: the fields RepoPilot reads, plus a few it should ignore."""

from typing import Any


def raw_pull_request(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": "https://api.github.com/repos/octo-org/widgets/pulls/42",
        "number": 42,
        "title": "Add retry logic to fetcher",
        "body": "Retries transient failures.",
        "state": "open",
        "draft": False,
        "merged": False,
        "user": {"login": "octocat", "id": 1},
        "html_url": "https://github.com/octo-org/widgets/pull/42",
        "base": {
            "ref": "main",
            "sha": "a" * 40,
            "repo": {
                "name": "widgets",
                "full_name": "octo-org/widgets",
                "owner": {"login": "octo-org"},
            },
        },
        "head": {
            "ref": "feature/retry",
            "sha": "b" * 40,
            "repo": {
                "name": "widgets",
                "full_name": "contrib/widgets",
                "owner": {"login": "contrib"},
            },
        },
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-02T08:30:00Z",
        "additions": 30,
        "deletions": 5,
        "changed_files": 2,
        "commits": 3,
        "labels": [],
    }
    payload.update(overrides)
    return payload


def raw_file(filename: str = "src/fetcher.py", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sha": "c" * 40,
        "filename": filename,
        "status": "modified",
        "additions": 10,
        "deletions": 2,
        "changes": 12,
        "blob_url": "https://github.com/octo-org/widgets/blob/main/" + filename,
        "patch": "@@ -1,2 +1,10 @@\n-old\n+new",
    }
    payload.update(overrides)
    return payload
