"""Evaluation runner, checks, metrics, and CLI with canned model output (no live AI)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.ai.base import AIUnavailableError, ModelReview, ModelTestSuggestion, ReviewPrompt
from app.services.ai.config import ReviewConfig
from app.services.evaluation import __main__ as cli
from app.services.evaluation.cases import (
    CLEAN_CHANGE,
    EVAL_CASES,
    INCOMPLETE_CONTEXT,
    MISSING_TEST,
    OBVIOUS_BUG,
)
from app.services.evaluation.checks import evaluate_conditions
from app.services.evaluation.runner import EvaluationRunner
from tests.review_helpers import FakeReviewModel, finding, make_engine, model_review, review_result

pytestmark = pytest.mark.anyio

CONFIG = ReviewConfig.from_settings(Settings(openai_api_key=None)).model_copy(
    update={"provider": "fake", "model": "fake-model"}
)

# What a well-behaved model should return for each case.
CANNED: dict[str, ModelReview] = {
    OBVIOUS_BUG.id: model_review(
        finding(
            title="Index out of range in last_item",
            file="src/collections_util.py",
            line_start=2,
            confidence=0.97,
        ),
        risk_level="high",
    ),
    MISSING_TEST.id: model_review(
        risk_level="medium",
        test_suggestions=(
            ModelTestSuggestion(description="Cover totals of 99.99, 100 and 100.01.", file=None),
        ),
    ),
    CLEAN_CHANGE.id: model_review(summary="Fixes a typo."),
    INCOMPLETE_CONTEXT.id: model_review(risk_level="medium"),
}

# A line unique to each case's diff, used to route the fake model to the right output.
MARKERS = {
    OBVIOUS_BUG.id: "items[len(items)]",
    MISSING_TEST.id: "total * 0.9",
    CLEAN_CHANGE.id: "Run the server",
    INCOMPLETE_CONTEXT.id: "retries: 5",
}


def canned_model(overrides: dict[str, ModelReview] | None = None) -> FakeReviewModel:
    outputs = CANNED | (overrides or {})

    def respond(prompt: ReviewPrompt) -> ModelReview:
        case_id = next(cid for cid, marker in MARKERS.items() if marker in prompt.input)
        return outputs[case_id]

    return FakeReviewModel(respond)


def runner(model: FakeReviewModel) -> EvaluationRunner:
    fixed = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    return EvaluationRunner(make_engine(model), CONFIG, now=lambda: fixed, clock=lambda: 0.0)


async def test_well_behaved_model_passes_every_case() -> None:
    run = await runner(canned_model()).run(EVAL_CASES)

    assert (run.total_cases, run.passed_cases, run.failed_cases, run.errored_cases) == (4, 4, 0, 0)
    assert run.metrics.case_pass_rate == 1.0
    assert all(c.passed and c.error is None for c in run.cases)
    assert run.model == "fake-model"
    assert run.prompt_version == CONFIG.prompt_version


async def test_failing_case_reports_failed_expectation() -> None:
    noisy = model_review(finding(title="Nitpick", file="docs/usage.md", line_start=2))

    run = await runner(canned_model({CLEAN_CHANGE.id: noisy})).run([CLEAN_CHANGE])

    (case,) = run.cases
    assert case.passed is False
    assert case.failed_expectations == ["expected <= 0 finding(s), got 1"]
    assert (run.passed_cases, run.failed_cases) == (0, 1)


async def test_missed_bug_fails_detection_condition() -> None:
    run = await runner(canned_model({OBVIOUS_BUG.id: model_review()})).run([OBVIOUS_BUG])

    (condition,) = run.cases[0].conditions
    assert (condition.kind, condition.passed) == ("detects_expected_bug", False)


async def test_aggregate_metrics_across_cases() -> None:
    overrides = {
        OBVIOUS_BUG.id: model_review(),  # misses the bug
        MISSING_TEST.id: model_review(),  # no test suggestion
    }

    run = await runner(canned_model(overrides)).run(EVAL_CASES)

    assert run.passed_cases == 2
    assert run.metrics.case_pass_rate == 0.5
    conditions = {k: (m.evaluated, m.passed) for k, m in run.metrics.conditions.items()}
    assert conditions == {
        "acknowledges_limitation": (1, 1),
        "detects_expected_bug": (1, 0),
        "finding_limit": (2, 2),
        "no_unreviewable_references": (1, 1),
        "suggests_test": (1, 0),
    }


async def test_metrics_are_deterministic() -> None:
    first = await runner(canned_model()).run(EVAL_CASES)
    second = await runner(canned_model()).run(EVAL_CASES)

    assert first.metrics == second.metrics
    assert [c.model_dump() for c in first.cases] == [c.model_dump() for c in second.cases]


async def test_provider_failure_is_recorded_as_sanitized_error() -> None:
    def fail(_: ReviewPrompt) -> ModelReview:
        raise AIUnavailableError()

    run = await runner(FakeReviewModel(fail)).run([OBVIOUS_BUG, CLEAN_CHANGE])

    assert (run.passed_cases, run.failed_cases, run.errored_cases) == (0, 0, 2)
    assert all(c.error == "The AI provider is unavailable." for c in run.cases)
    assert all(c.review is None and c.conditions == [] for c in run.cases)
    assert run.metrics.case_pass_rate == 0.0
    assert run.metrics.conditions == {}


async def test_fabricated_reference_to_missing_diff_is_neutralized() -> None:
    fabricated = finding(
        title="SQL injection in processor",
        category="security",
        file="src/payments/processor.py",
        line_start=120,
    )

    run = await runner(canned_model({INCOMPLETE_CONTEXT.id: model_review(fabricated)})).run(
        [INCOMPLETE_CONTEXT]
    )

    (case,) = run.cases
    assert case.review is not None
    (f,) = case.review.findings
    assert (f.file, f.line_start) == (None, None)
    # The finding still counts against the finding limit, but never as a located claim.
    assert {c.kind for c in case.conditions if not c.passed} == {"finding_limit"}


def test_conditions_only_cover_defined_expectations() -> None:
    conditions = evaluate_conditions(review_result(), MISSING_TEST.expectations)

    assert [(c.kind, c.passed) for c in conditions] == [("suggests_test", False)]


def test_case_ids_are_unique() -> None:
    assert len({case.id for case in EVAL_CASES}) == len(EVAL_CASES)


# --- CLI --------------------------------------------------------------------------------


async def test_cli_without_api_key_exits_with_config_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = await cli.run(cli.parse_args(["--no-persist"]), Settings(openai_api_key=None))

    assert code == cli.EXIT_CONFIG
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err


async def test_cli_success_writes_json_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "run.json"

    code = await cli.run(
        cli.parse_args(["--no-persist", "--json", str(out)]),
        Settings(openai_api_key="sk-test-sentinel-key"),
        engine=make_engine(canned_model()),
    )

    assert code == cli.EXIT_OK
    text = out.read_text(encoding="utf-8")
    assert json.loads(text)["passed_cases"] == 4
    assert "sk-test-sentinel-key" not in text
    assert "PASS  obvious_bug" in capsys.readouterr().out


async def test_cli_failures_exit_nonzero() -> None:
    code = await cli.run(
        cli.parse_args(["--no-persist"]),
        Settings(openai_api_key=None),
        engine=make_engine(canned_model({OBVIOUS_BUG.id: model_review()})),
    )

    assert code == cli.EXIT_FAILED


async def test_cli_storage_failure_is_reported_safely(capsys: pytest.CaptureFixture[str]) -> None:
    unreachable = "postgresql+psycopg://nobody:secret-db-password@127.0.0.1:1/nothing_test"

    code = await cli.run(
        cli.parse_args([]),
        Settings(openai_api_key=None, database_url=unreachable),
        engine=make_engine(canned_model()),
    )

    assert code == cli.EXIT_CONFIG
    err = capsys.readouterr().err
    assert "Review storage is unavailable." in err
    assert "secret-db-password" not in err
