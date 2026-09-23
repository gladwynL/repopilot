from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.review import GitHubReviewRequest, ReviewFinding, ReviewResult
from app.services.ai.base import ModelReview


def finding_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "category": "bug",
        "severity": "high",
        "confidence": 0.8,
        "title": "t",
        "description": "d",
        "suggestion": "s",
        "file": "a.py",
        "line_start": 3,
        "line_end": 5,
    }
    data.update(overrides)
    return data


def test_valid_review_result() -> None:
    result = ReviewResult.model_validate(
        {
            "pull_request": {"owner": "o", "repo": "r", "number": 1, "head_sha": "abc"},
            "model": "m",
            "prompt_version": "v1",
            "summary": "s",
            "risk_level": "medium",
            "findings": [finding_data()],
            "test_suggestions": [{"description": "test x", "file": None}],
            "reviewed_files": ["a.py"],
            "truncated_files": [],
            "skipped_files": [{"filename": "logo.png", "reason": "no_patch"}],
            "limitations": [],
        }
    )

    assert result.findings[0].line_end == 5


@pytest.mark.parametrize(
    "overrides",
    [
        {"severity": "blocker"},
        {"category": "style"},
        {"confidence": 1.5},
        {"confidence": -0.1},
        {"line_start": 0},
        {"line_start": None, "line_end": 4},
        {"line_start": 5, "line_end": 3},
        {"file": None},
    ],
)
def test_invalid_finding_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(finding_data(**overrides))


def test_line_references_are_optional() -> None:
    finding = ReviewFinding.model_validate(finding_data(line_start=None, line_end=None))

    assert finding.line_start is None


def test_pr_wide_finding_without_file() -> None:
    finding = ReviewFinding.model_validate(finding_data(file=None, line_start=None, line_end=None))

    assert finding.file is None


def test_model_review_allows_empty_findings() -> None:
    review = ModelReview.model_validate(
        {
            "summary": "Clean.",
            "risk_level": "low",
            "findings": [],
            "test_suggestions": [],
            "limitations": [],
        }
    )

    assert review.findings == []


def test_model_review_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ModelReview.model_validate(
            {
                "summary": "s",
                "risk_level": "low",
                "findings": [],
                "test_suggestions": [],
                "limitations": [],
                "verdict": "approve",
            }
        )


@pytest.mark.parametrize(
    "body",
    [
        {"owner": "-bad", "repo": "r", "pull_number": 1},
        {"owner": "o", "repo": "..", "pull_number": 1},
        {"owner": "o", "repo": "r", "pull_number": 0},
        {"owner": "o", "repo": "r"},
    ],
)
def test_review_request_validation(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GitHubReviewRequest.model_validate(body)
