import random

import pytest

from app.services.ai.input_builder import (
    estimate_tokens,
    is_generated,
    is_test,
    priority_key,
)
from app.services.ai.prompts import (
    BODY_MAX_CHARS,
    REVIEW_INSTRUCTIONS,
    build_review_prompt,
)
from tests.review_helpers import SIMPLE_PATCH, big_patch, make_builder, make_file, make_pr


def prompt_text(pr_files: tuple, **options: int) -> str:
    review_input = make_builder(**options).build(make_pr(*pr_files))
    return build_review_prompt(review_input, 0).input


def test_pr_metadata_in_context() -> None:
    review_input = make_builder().build(make_pr(make_file()))

    context = review_input.context
    assert "Pull request: octo-org/widgets#42" in context
    assert "Title: Add retry logic to fetcher" in context
    assert "Branches: feature/retry -> main" in context
    assert "Retries transient failures." in context
    assert "- src/app.py (modified, +2/-1): reviewed" in context


def test_long_description_is_truncated() -> None:
    review_input = make_builder().build(make_pr(make_file(), body="d" * (BODY_MAX_CHARS + 500)))

    assert "[description truncated]" in review_input.context
    assert "d" * (BODY_MAX_CHARS + 1) not in review_input.context


def test_patch_rendered_with_new_file_line_numbers() -> None:
    text = prompt_text((make_file(),))

    assert '<file path="src/app.py" status="modified" additions=2 deletions=1>' in text
    assert "    1   import os" in text
    assert "      - x = 1" in text
    assert "    2 + x = 2" in text
    assert "    4   print(x)" in text


def test_prompt_separates_stable_instructions_from_pr_input() -> None:
    review_input = make_builder().build(make_pr(make_file()))
    prompt = build_review_prompt(review_input, 0)

    assert prompt.instructions == REVIEW_INSTRUCTIONS
    assert "src/app.py" not in prompt.instructions
    assert "Never guess a line number" in prompt.instructions
    assert "zero findings" in prompt.instructions


def test_renamed_file_shows_previous_path() -> None:
    text = prompt_text((make_file("new.py", status="renamed", previous_filename="old.py"),))

    assert 'previous_path="old.py"' in text


def test_missing_patch_is_skipped_and_recorded() -> None:
    pr = make_pr(make_file(), make_file("assets/logo.png", patch=None, status="added"))

    review_input = make_builder().build(pr)

    assert [f.filename for f in review_input.reviewed_files] == ["src/app.py"]
    assert [(s.filename, s.reason) for s in review_input.skipped_files] == [
        ("assets/logo.png", "no_patch")
    ]
    assert any("assets/logo.png" in lim for lim in review_input.limitations)
    assert "assets/logo.png (added, +2/-1): not reviewed: no diff available" in (
        review_input.context
    )


def test_only_missing_patches_produces_no_chunks() -> None:
    review_input = make_builder().build(make_pr(make_file("a.bin", patch=None)))

    assert review_input.chunks == ()


def test_generated_files_skipped() -> None:
    pr = make_pr(make_file(), make_file("frontend/package-lock.json"))

    review_input = make_builder().build(pr)

    assert ("frontend/package-lock.json", "generated") in [
        (s.filename, s.reason) for s in review_input.skipped_files
    ]


@pytest.mark.parametrize(
    ("path", "generated"),
    [
        ("yarn.lock", True),
        ("static/app.min.js", True),
        ("vendor/lib/x.go", True),
        ("api/foo_pb2.py", True),
        ("src/vendors.py", False),
        ("src/app.py", False),
    ],
)
def test_is_generated(path: str, generated: bool) -> None:
    assert is_generated(path) is generated


@pytest.mark.parametrize(
    ("path", "test"),
    [
        ("tests/test_api.py", True),
        ("src/foo_test.go", True),
        ("src/Button.test.tsx", True),
        ("src/latest.py", False),
        ("src/contest/app.py", False),
    ],
)
def test_is_test(path: str, test: bool) -> None:
    assert is_test(path) is test


def test_priority_order_is_documented_tiers_then_size_then_name() -> None:
    files = [
        make_file("README.md", additions=50),
        make_file("tests/test_app.py", additions=40),
        make_file("Dockerfile", additions=1),
        make_file("src/small.py", additions=1),
        make_file("src/big.py", additions=30),
        make_file("src/old.py", status="removed", additions=0, deletions=90),
        make_file("src/also_small.py", additions=1),
    ]

    ordered = [f.filename for f in sorted(files, key=priority_key)]

    assert ordered == [
        "src/big.py",
        "src/also_small.py",
        "src/small.py",
        "Dockerfile",
        "tests/test_app.py",
        "README.md",
        "src/old.py",
    ]


def test_build_is_deterministic_regardless_of_input_order() -> None:
    files = [make_file(f"src/m{i}.py", big_patch(20 + i)) for i in range(12)]
    shuffled = files[:]
    random.Random(7).shuffle(shuffled)
    builder = make_builder(chunk_token_budget=8_000, max_chunks=2)

    first = builder.build(make_pr(*files))
    second = builder.build(make_pr(*shuffled))

    assert [[f.filename for f in c.files] for c in first.chunks] == [
        [f.filename for f in c.files] for c in second.chunks
    ]
    assert builder.build(make_pr(*files)) == first


def test_every_chunk_prompt_fits_budget() -> None:
    budget = 8_000
    files = [make_file(f"src/m{i:02}.py", big_patch(60)) for i in range(40)]
    review_input = make_builder(chunk_token_budget=budget, max_chunks=3).build(make_pr(*files))

    assert len(review_input.chunks) == 3
    for index in range(len(review_input.chunks)):
        assert estimate_tokens(build_review_prompt(review_input, index).input) <= budget


def test_over_budget_files_are_skipped_and_recorded() -> None:
    files = [make_file(f"src/m{i:02}.py", big_patch(60)) for i in range(40)]

    review_input = make_builder(chunk_token_budget=8_000, max_chunks=1).build(make_pr(*files))

    over = [s.filename for s in review_input.skipped_files if s.reason == "over_budget"]
    assert over
    assert len(review_input.reviewed_files) + len(over) == 40
    assert any("exceeds the review budget" in lim for lim in review_input.limitations)
    assert "not reviewed: exceeded the review budget" in review_input.context


def test_multiple_chunks_record_limitation() -> None:
    files = [make_file(f"src/m{i:02}.py", big_patch(60)) for i in range(20)]

    review_input = make_builder(chunk_token_budget=8_000, max_chunks=3).build(make_pr(*files))

    assert len(review_input.chunks) > 1
    assert any("separate parts" in lim for lim in review_input.limitations)
    assert "part 1 of" in build_review_prompt(review_input, 0).input


def test_oversized_file_is_truncated_at_line_boundary() -> None:
    pr = make_pr(make_file("src/huge.py", big_patch(2_000)))

    review_input = make_builder(max_file_tokens=1_000).build(pr)

    (file,) = review_input.reviewed_files
    assert file.truncated
    assert 0 < len(file.lines) < 2_001
    assert max(file.new_lines) < 2_000  # lines beyond the cut are not citable
    text = build_review_prompt(review_input, 0).input
    assert f"[diff truncated: {file.omitted_lines} more lines not shown]" in text
    assert "src/huge.py (modified, +2/-1): reviewed (diff truncated)" in review_input.context
    assert any("Only the beginning" in lim for lim in review_input.limitations)


def test_github_file_cap_recorded() -> None:
    pr = make_pr(make_file())
    pr = pr.model_copy(update={"metadata": pr.metadata.model_copy(update={"changed_files": 3_500})})

    review_input = make_builder().build(pr)

    assert any("GitHub returned 1 of 3500" in lim for lim in review_input.limitations)


def test_simple_patch_new_lines() -> None:
    review_input = make_builder().build(make_pr(make_file(patch=SIMPLE_PATCH)))

    assert review_input.reviewed_files[0].new_lines == frozenset({1, 2, 3, 4})
