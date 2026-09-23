import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_review_repository, get_review_service
from app.repositories.reviews import ReviewRepository
from app.schemas.pull_request import (
    GITHUB_OWNER_MAX_LENGTH,
    GITHUB_OWNER_PATTERN,
    GITHUB_REPO_MAX_LENGTH,
    GITHUB_REPO_PATTERN,
)
from app.schemas.review import (
    GitHubReviewRequest,
    ReviewHistoryPage,
    ReviewRunResponse,
    StoredReview,
)
from app.services.reviews import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])

MAX_PAGE_SIZE = 100


@router.post("/github", response_model=ReviewRunResponse)
async def review_github_pull_request(
    request: GitHubReviewRequest,
    service: Annotated[ReviewService, Depends(get_review_service)],
    force: Annotated[
        bool, Query(description="Run a fresh review even if a cached one exists.")
    ] = False,
) -> ReviewRunResponse:
    return await service.review_pull_request(
        request.owner, request.repo, request.pull_number, force=force
    )


@router.get("", response_model=ReviewHistoryPage)
def list_reviews(
    repository: Annotated[ReviewRepository, Depends(get_review_repository)],
    owner: Annotated[
        str | None,
        Query(max_length=GITHUB_OWNER_MAX_LENGTH, pattern=GITHUB_OWNER_PATTERN),
    ] = None,
    repo: Annotated[
        str | None,
        Query(max_length=GITHUB_REPO_MAX_LENGTH, pattern=GITHUB_REPO_PATTERN),
    ] = None,
    pull_number: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewHistoryPage:
    return repository.list(
        owner=owner, repo=repo, pull_number=pull_number, limit=limit, offset=offset
    )


@router.get("/{review_id}", response_model=StoredReview)
def get_review(
    review_id: uuid.UUID,
    repository: Annotated[ReviewRepository, Depends(get_review_repository)],
) -> StoredReview:
    review = repository.get(review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return review
