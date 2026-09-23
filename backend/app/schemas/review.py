"""RepoPilot's public review contract returned by the review API."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.pull_request import (
    GITHUB_OWNER_MAX_LENGTH,
    GITHUB_OWNER_PATTERN,
    GITHUB_REPO_MAX_LENGTH,
    GITHUB_REPO_PATTERN,
)

Severity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]
FindingCategory = Literal[
    "bug", "security", "reliability", "performance", "maintainability", "code_quality", "testing"
]
SkipReason = Literal["no_patch", "generated", "over_budget"]

SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ReviewFinding(_Frozen):
    category: FindingCategory
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    suggestion: str
    file: str | None
    """Path in the PR; ``None`` for PR-wide findings or when no reviewed file could be matched."""
    line_start: int | None = Field(default=None, ge=1)
    """Line in the new version of ``file``. Only set when it appears in the reviewed diff."""
    line_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def check_line_range(self) -> Self:
        if self.line_end is not None and (
            self.line_start is None or self.line_end < self.line_start
        ):
            raise ValueError("line_end requires line_start and must not precede it")
        if self.line_start is not None and self.file is None:
            raise ValueError("line references require a file")
        return self


class TestSuggestion(_Frozen):
    __test__ = False  # not a pytest test class

    description: str
    file: str | None


class SkippedFile(_Frozen):
    filename: str
    reason: SkipReason


class ReviewedPullRequest(_Frozen):
    owner: str
    repo: str
    number: int
    head_sha: str


class ReviewResult(_Frozen):
    pull_request: ReviewedPullRequest
    model: str
    prompt_version: str
    summary: str
    risk_level: RiskLevel | None
    """``None`` when no diff content could be reviewed, so no assessment was made."""
    findings: list[ReviewFinding]
    test_suggestions: list[TestSuggestion]
    reviewed_files: list[str]
    truncated_files: list[str]
    """Reviewed files whose diff was cut to fit the budget; only the start was reviewed."""
    skipped_files: list[SkippedFile]
    limitations: list[str]


class StoredReview(_Frozen):
    """A persisted review: the Phase 2 ``ReviewResult`` plus storage metadata."""

    id: UUID
    created_at: datetime
    is_current: bool
    """Whether cache lookups currently return this review for its PR commit and config."""
    review: ReviewResult


class ReviewRunResponse(StoredReview):
    cached: bool
    """True when an existing review was returned and no model call was made."""


class ReviewSummary(_Frozen):
    id: UUID
    owner: str
    repo: str
    pull_number: int
    head_sha: str
    provider: str
    model: str
    prompt_version: str
    risk_level: RiskLevel | None
    finding_count: int
    is_current: bool
    created_at: datetime


class ReviewHistoryPage(_Frozen):
    items: list[ReviewSummary]
    total: int
    limit: int
    offset: int


class GitHubReviewRequest(BaseModel):
    owner: str = Field(
        min_length=1, max_length=GITHUB_OWNER_MAX_LENGTH, pattern=GITHUB_OWNER_PATTERN
    )
    repo: str = Field(min_length=1, max_length=GITHUB_REPO_MAX_LENGTH, pattern=GITHUB_REPO_PATTERN)
    pull_number: int = Field(ge=1)
