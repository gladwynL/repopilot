from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_github_client, get_review_engine
from app.schemas.review import GitHubReviewRequest, ReviewResult
from app.services.ai.review_engine import ReviewEngine
from app.services.github import GitHubClient

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/github", response_model=ReviewResult)
async def review_github_pull_request(
    request: GitHubReviewRequest,
    engine: Annotated[ReviewEngine, Depends(get_review_engine)],
    github: Annotated[GitHubClient, Depends(get_github_client)],
) -> ReviewResult:
    pr = await github.get_pull_request(request.owner, request.repo, request.pull_number)
    return await engine.review_pull_request(pr)
