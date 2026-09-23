import pytest

from app.services.ai.base import AIUnavailableError, ModelTestSuggestion, ReviewPrompt
from app.services.ai.review_engine import NOTHING_TO_REVIEW_SUMMARY
from tests.review_helpers import (
    FakeReviewModel,
    big_patch,
    finding,
    make_engine,
    make_file,
    make_pr,
    model_review,
)

pytestmark = pytest.mark.anyio


async def test_simple_review() -> None:
    model = FakeReviewModel(model_review(finding(), risk_level="medium"))

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    assert len(model.prompts) == 1
    assert result.pull_request.number == 42
    assert result.pull_request.head_sha == "b" * 40
    assert result.model == "fake-model"
    assert result.risk_level == "medium"
    assert result.reviewed_files == ["src/app.py"]
    (f,) = result.findings
    assert (f.file, f.line_start, f.category) == ("src/app.py", 2, "bug")


async def test_zero_findings_is_a_valid_review() -> None:
    model = FakeReviewModel(model_review(summary="Clean refactor."))

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    assert result.findings == []
    assert result.summary == "Clean refactor."
    assert result.risk_level == "low"


async def test_findings_sorted_by_severity_then_confidence() -> None:
    model = FakeReviewModel(
        model_review(
            finding(title="minor", severity="low", confidence=0.9),
            finding(title="major", severity="critical", confidence=0.7),
            finding(title="sure", severity="high", confidence=0.95),
            finding(title="unsure", severity="high", confidence=0.6),
        )
    )

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    assert [f.title for f in result.findings] == ["major", "sure", "unsure", "minor"]


async def test_line_not_in_diff_is_nulled_not_fabricated() -> None:
    model = FakeReviewModel(
        model_review(
            finding(title="outside diff", line_start=40),
            finding(title="bad range", line_start=2, line_end=99),
            finding(title="valid range", line_start=2, line_end=3),
        )
    )

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    by_title = {f.title: f for f in result.findings}
    assert (by_title["outside diff"].line_start, by_title["outside diff"].line_end) == (None, None)
    assert (by_title["bad range"].line_start, by_title["bad range"].line_end) == (2, None)
    assert (by_title["valid range"].line_start, by_title["valid range"].line_end) == (2, 3)
    assert all(f.file == "src/app.py" for f in result.findings)


async def test_removed_line_cannot_be_cited() -> None:
    # SIMPLE_PATCH removes old line 2 ("x = 1"); new line numbers are 1-4 only.
    model = FakeReviewModel(model_review(finding(line_start=5)))

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    assert result.findings[0].line_start is None


async def test_unknown_file_reference_is_dropped() -> None:
    model = FakeReviewModel(model_review(finding(file="src/imaginary.py", line_start=2)))

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    (f,) = result.findings
    assert (f.file, f.line_start) == (None, None)


async def test_low_confidence_findings_filtered() -> None:
    model = FakeReviewModel(
        model_review(finding(title="speculative", confidence=0.2), finding(title="solid"))
    )

    result = await make_engine(model, min_confidence=0.3).review_pull_request(make_pr(make_file()))

    assert [f.title for f in result.findings] == ["solid"]


async def test_duplicate_findings_collapse_to_strongest() -> None:
    model = FakeReviewModel(
        model_review(
            finding(title="Off-by-one in loop", severity="medium", confidence=0.8),
            finding(title="off by one in loop!", severity="high", confidence=0.7),
            finding(title="Off-by-one in loop", category="testing"),
        )
    )

    result = await make_engine(model).review_pull_request(make_pr(make_file()))

    assert [(f.category, f.severity, f.confidence) for f in result.findings] == [
        ("testing", "high", 0.9),
        ("bug", "high", 0.7),
    ]


async def test_chunked_review_merges_and_deduplicates() -> None:
    files = [make_file(f"src/m{i:02}.py", big_patch(60)) for i in range(12)]
    pr_wide = finding(title="Missing error handling", file=None, line_start=None)

    def respond(prompt: ReviewPrompt):  # type: ignore[no-untyped-def]
        first_file = prompt.input.split('<file path="')[1].split('"')[0]
        return model_review(
            pr_wide,
            finding(title=f"Bug in {first_file}", file=first_file, line_start=1),
            summary=f"Part covering {first_file}.",
            risk_level="high" if first_file == "src/m00.py" else "low",
            test_suggestions=(ModelTestSuggestion(description="Test retries", file=None),),
            limitations=("Callers of changed functions were not visible.",),
        )

    model = FakeReviewModel(respond)
    result = await make_engine(model, chunk_token_budget=8_000, max_chunks=3).review_pull_request(
        make_pr(*files)
    )

    assert len(model.prompts) > 1
    assert result.risk_level == "high"
    assert [f.title for f in result.findings].count("Missing error handling") == 1
    assert len(result.findings) == len(model.prompts) + 1
    assert len(result.test_suggestions) == 1
    assert result.summary.count("Part covering") == len(model.prompts)
    assert result.limitations.count("Callers of changed functions were not visible.") == 1
    assert any("separate parts" in lim for lim in result.limitations)


async def test_input_limitations_and_skipped_files_preserved() -> None:
    model = FakeReviewModel(model_review(limitations=("Model saw partial context.",)))
    pr = make_pr(make_file(), make_file("img.png", patch=None), make_file("yarn.lock"))

    result = await make_engine(model).review_pull_request(pr)

    assert [(s.filename, s.reason) for s in result.skipped_files] == [
        ("img.png", "no_patch"),
        ("yarn.lock", "generated"),
    ]
    assert any("img.png" in lim for lim in result.limitations)
    assert "Model saw partial context." in result.limitations


async def test_nothing_reviewable_skips_model_call() -> None:
    model = FakeReviewModel(model_review(finding()))

    result = await make_engine(model).review_pull_request(make_pr(make_file("a.bin", patch=None)))

    assert model.prompts == []
    assert result.summary == NOTHING_TO_REVIEW_SUMMARY
    assert result.risk_level is None
    assert result.findings == []
    assert result.reviewed_files == []


async def test_review_is_deterministic() -> None:
    files = [make_file(f"src/m{i:02}.py", big_patch(60)) for i in range(8)]
    model = FakeReviewModel(model_review(finding(file="src/m03.py", line_start=5)))
    engine = make_engine(model, chunk_token_budget=8_000)

    first = await engine.review_pull_request(make_pr(*files))
    second = await engine.review_pull_request(make_pr(*reversed(files)))

    assert first == second


async def test_provider_failure_propagates() -> None:
    def fail(_: ReviewPrompt):  # type: ignore[no-untyped-def]
        raise AIUnavailableError()

    with pytest.raises(AIUnavailableError):
        await make_engine(FakeReviewModel(fail)).review_pull_request(make_pr(make_file()))


async def test_completion_log_has_metadata_but_no_diff_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_line = "SENSITIVE_SOURCE_LINE"
    pr = make_pr(make_file(patch=f"@@ -1 +1 @@\n-a\n+{secret_line}"))
    model = FakeReviewModel(model_review(finding(line_start=1)))

    with caplog.at_level("INFO", logger="app.services.ai.review_engine"):
        await make_engine(model).review_pull_request(pr)

    (record,) = caplog.records
    message = record.getMessage()
    assert "pr=octo-org/widgets#42" in message
    assert "files_sent=1" in message
    assert "chunks=1" in message
    assert secret_line not in message
    assert "Retries transient failures." not in message  # PR description
