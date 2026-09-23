"""Deterministic review evaluation cases.

Each case pairs a small PR with the output a well-behaved model *should* return and the
expectations a review must meet. With canned outputs these exercise the pipeline (prompt
content, grounding, merging), not model quality. ``check_expectations`` is written so the
same cases can later be run against a live model.
"""

from dataclasses import dataclass, field

from app.schemas.pull_request import PullRequest
from app.schemas.review import ReviewResult
from app.services.ai.base import ModelReview, ModelTestSuggestion
from tests.review_helpers import finding, make_file, make_pr, model_review


@dataclass(frozen=True)
class Expectations:
    min_high_confidence_bugs: int = 0
    max_findings: int | None = None
    requires_test_suggestion: bool = False
    limitation_mentions: tuple[str, ...] = ()
    unreviewable_files: tuple[str, ...] = ()
    """Files without a diff: no finding may reference them."""


@dataclass(frozen=True)
class EvalCase:
    name: str
    pr: PullRequest
    canned_output: ModelReview
    expectations: Expectations
    prompt_must_contain: tuple[str, ...] = field(default=())


def check_expectations(result: ReviewResult, expected: Expectations) -> list[str]:
    problems = []
    strong_bugs = [f for f in result.findings if f.category == "bug" and f.confidence >= 0.8]
    if len(strong_bugs) < expected.min_high_confidence_bugs:
        problems.append(f"expected >= {expected.min_high_confidence_bugs} high-confidence bugs")
    if expected.max_findings is not None and len(result.findings) > expected.max_findings:
        problems.append(f"expected <= {expected.max_findings} findings")
    if expected.requires_test_suggestion and not result.test_suggestions:
        problems.append("expected a test suggestion")
    for text in expected.limitation_mentions:
        if not any(text in limitation for limitation in result.limitations):
            problems.append(f"expected a limitation mentioning {text!r}")
    for name in expected.unreviewable_files:
        if any(f.file == name for f in result.findings):
            problems.append(f"finding references unreviewable file {name}")
    return problems


OBVIOUS_BUG = EvalCase(
    name="A: obvious bug",
    pr=make_pr(
        make_file(
            "src/collections_util.py",
            "@@ -1,3 +1,3 @@\n def last_item(items):\n-    return items[-1]\n"
            "+    return items[len(items)]\n",
            additions=1,
            deletions=1,
        ),
        title="Simplify last_item",
        body="Use explicit indexing.",
    ),
    canned_output=model_review(
        finding(
            title="Index out of range in last_item",
            description="items[len(items)] is always one past the end and raises IndexError.",
            suggestion="Use items[-1] and handle empty input explicitly.",
            file="src/collections_util.py",
            line_start=2,
            confidence=0.97,
        ),
        summary="Changes last_item to explicit indexing, which introduces an IndexError.",
        risk_level="high",
    ),
    expectations=Expectations(min_high_confidence_bugs=1),
    prompt_must_contain=("    2 +     return items[len(items)]",),
)

MISSING_TEST = EvalCase(
    name="B: behavior change without tests",
    pr=make_pr(
        make_file(
            "src/pricing.py",
            "@@ -1,2 +1,4 @@\n def discount(total):\n+    if total >= 100:\n"
            "+        return total * 0.9\n     return total\n",
            additions=2,
            deletions=0,
        ),
        title="Add 10% discount for orders over 100",
    ),
    canned_output=model_review(
        summary="Adds a 10% discount for totals of 100 or more.",
        risk_level="medium",
        test_suggestions=(
            ModelTestSuggestion(
                description="Cover totals of 99.99, 100, and 100.01 for the discount boundary.",
                file="tests/test_pricing.py",
            ),
        ),
    ),
    expectations=Expectations(requires_test_suggestion=True),
    prompt_must_contain=("    2 +     if total >= 100:",),
)

CLEAN_CHANGE = EvalCase(
    name="C: clean change",
    pr=make_pr(
        make_file(
            "docs/usage.md",
            "@@ -1,2 +1,2 @@\n # Usage\n-Run the sever with make run.\n"
            "+Run the server with make run.\n",
            additions=1,
            deletions=1,
        ),
        title="Fix typo in usage docs",
    ),
    canned_output=model_review(summary="Fixes a typo in the usage documentation."),
    expectations=Expectations(max_findings=0),
)

INCOMPLETE_CONTEXT = EvalCase(
    name="D: incomplete context",
    pr=make_pr(
        make_file("src/payments/processor.py", patch=None, additions=900, deletions=400),
        make_file(
            "config/settings.yaml",
            "@@ -1 +1 @@\n-retries: 3\n+retries: 5\n",
            additions=1,
            deletions=1,
        ),
        title="Rework payment processor",
    ),
    canned_output=model_review(
        summary="Raises retries to 5; the main processor change could not be reviewed.",
        risk_level="medium",
        limitations=("The diff for src/payments/processor.py was not available.",),
    ),
    expectations=Expectations(
        max_findings=0,
        limitation_mentions=("src/payments/processor.py",),
        unreviewable_files=("src/payments/processor.py",),
    ),
    prompt_must_contain=(
        "src/payments/processor.py (modified, +900/-400): not reviewed: no diff available",
    ),
)

EVAL_CASES = (OBVIOUS_BUG, MISSING_TEST, CLEAN_CHANGE, INCOMPLETE_CONTEXT)
