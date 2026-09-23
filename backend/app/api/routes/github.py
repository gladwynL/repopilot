from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_github_client
from app.schemas.pull_request import (
    GITHUB_OWNER_MAX_LENGTH,
    GITHUB_OWNER_PATTERN,
    GITHUB_REPO_MAX_LENGTH,
    GITHUB_REPO_PATTERN,
    PullRequest,
)
from app.services.github import GitHubClient

router = APIRouter(prefix="/github", tags=["github"])

Owner = Annotated[
    str, Path(min_length=1, max_length=GITHUB_OWNER_MAX_LENGTH, pattern=GITHUB_OWNER_PATTERN)
]
Repo = Annotated[
    str, Path(min_length=1, max_length=GITHUB_REPO_MAX_LENGTH, pattern=GITHUB_REPO_PATTERN)
]
PullNumber = Annotated[int, Path(ge=1)]


@router.get("/repos/{owner}/{repo}/pulls/{pull_number}", response_model=PullRequest)
async def get_pull_request(
    owner: Owner,
    repo: Repo,
    pull_number: PullNumber,
    github: Annotated[GitHubClient, Depends(get_github_client)],
) -> PullRequest:
    return await github.get_pull_request(owner, repo, pull_number)
