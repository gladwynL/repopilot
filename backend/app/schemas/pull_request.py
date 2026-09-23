"""Normalized pull request representation owned by RepoPilot.

These models are the contract between GitHub ingestion and downstream consumers
(the API today, the review engine later). Raw GitHub payloads never leave
``app.services.github``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

GITHUB_OWNER_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
GITHUB_OWNER_MAX_LENGTH = 39
# Must contain at least one alphanumeric so "." and ".." are rejected.
GITHUB_REPO_PATTERN = r"^[A-Za-z0-9._-]*[A-Za-z0-9][A-Za-z0-9._-]*$"
GITHUB_REPO_MAX_LENGTH = 100

PullRequestState = Literal["open", "closed"]
FileStatus = Literal["added", "removed", "modified", "renamed", "copied", "changed", "unchanged"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class GitRef(_Frozen):
    ref: str
    sha: str
    repo_full_name: str | None
    """``owner/name`` of the repository holding the ref; differs from the base for forks
    and is ``None`` when the fork has been deleted."""


class PullRequestMetadata(_Frozen):
    owner: str
    repo: str
    number: int
    title: str
    body: str | None
    state: PullRequestState
    draft: bool
    merged: bool
    author_login: str | None
    html_url: str
    base: GitRef
    head: GitRef
    created_at: datetime
    updated_at: datetime
    additions: int
    deletions: int
    changed_files: int
    commits: int


class PullRequestFile(_Frozen):
    filename: str
    status: FileStatus
    additions: int
    deletions: int
    changes: int
    sha: str | None
    patch: str | None
    """Unified diff hunk text. GitHub omits it for binary files and very large diffs."""
    previous_filename: str | None


class PullRequest(_Frozen):
    metadata: PullRequestMetadata
    files: list[PullRequestFile]
