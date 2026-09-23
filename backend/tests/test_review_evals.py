"""Pipeline checks over the evaluation cases, using canned model output (no live AI)."""

import pytest

from app.schemas.review import ReviewedPullRequest, ReviewResult
from tests.review_eval_cases import EVAL_CASES, INCOMPLETE_CONTEXT, EvalCase, check_expectations
from tests.review_helpers import FakeReviewModel, finding, make_engine, model_review

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("case", EVAL_CASES, ids=lambda case: case.name)
async def test_case_meets_expectations(case: EvalCase) -> None:
    model = FakeReviewModel(case.canned_output)

    result = await make_engine(model).review_pull_request(case.pr)

    assert check_expectations(result, case.expectations) == []
    (prompt,) = model.prompts
    for text in case.prompt_must_contain:
        assert text in prompt.input


async def test_fabricated_reference_to_missing_diff_is_neutralized() -> None:
    """A model that invents a finding on a file it never saw must not produce a located claim."""
    fabricated = finding(
        title="SQL injection in processor",
        category="security",
        file="src/payments/processor.py",
        line_start=120,
    )
    model = FakeReviewModel(model_review(fabricated))

    result = await make_engine(model).review_pull_request(INCOMPLETE_CONTEXT.pr)

    (f,) = result.findings
    assert (f.file, f.line_start) == (None, None)
    assert check_expectations(result, INCOMPLETE_CONTEXT.expectations) == ["expected <= 0 findings"]


def test_evaluator_flags_missing_expectations() -> None:
    empty = ReviewResult(
        pull_request=ReviewedPullRequest(owner="o", repo="r", number=1, head_sha="s"),
        model="m",
        prompt_version="v",
        summary="s",
        risk_level="low",
        findings=[],
        test_suggestions=[],
        reviewed_files=[],
        truncated_files=[],
        skipped_files=[],
        limitations=[],
    )

    problems = check_expectations(empty, EVAL_CASES[0].expectations)

    assert problems == ["expected >= 1 high-confidence bugs"]
