"""Builders and fakes shared by the review-engine tests. No network or paid API calls."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx
from openai import AsyncOpenAI

from app.schemas.pull_request import PullRequest, PullRequestFile
from app.schemas.review import (
    ReviewedPullRequest,
    ReviewHistoryPage,
    ReviewResult,
    ReviewSummary,
    StoredReview,
)
from app.services.ai.base import (
    ModelFinding,
    ModelReview,
    ModelTestSuggestion,
    ReviewPrompt,
)
from app.services.ai.input_builder import ReviewInputBuilder
from app.services.ai.openai_provider import OpenAIReviewModel
from app.services.ai.review_engine import ReviewEngine
from app.services.github import normalize_metadata
from tests.github_payloads import raw_pull_request

SIMPLE_PATCH = "@@ -1,3 +1,4 @@\n import os\n-x = 1\n+x = 2\n+y = 3\n print(x)"
"""New-file lines: 1 (context), 2 and 3 (added), 4 (context)."""


def make_file(
    filename: str = "src/app.py",
    patch: str | None = SIMPLE_PATCH,
    *,
    status: str = "modified",
    additions: int = 2,
    deletions: int = 1,
    previous_filename: str | None = None,
) -> PullRequestFile:
    return PullRequestFile(
        filename=filename,
        status=status,  # type: ignore[arg-type]
        additions=additions,
        deletions=deletions,
        changes=additions + deletions,
        sha="c" * 40,
        patch=patch,
        previous_filename=previous_filename,
    )


def make_pr(*files: PullRequestFile, **metadata: Any) -> PullRequest:
    raw = raw_pull_request(changed_files=len(files), **metadata)
    return PullRequest(metadata=normalize_metadata(raw), files=list(files))


def big_patch(lines: int, width: int = 60) -> str:
    body = "\n".join(f"+{'x' * width} {i}" for i in range(lines))
    return f"@@ -0,0 +1,{lines} @@\n{body}"


def finding(**overrides: Any) -> ModelFinding:
    values: dict[str, Any] = {
        "category": "bug",
        "severity": "high",
        "confidence": 0.9,
        "title": "Off-by-one in loop",
        "description": "The loop skips the last element.",
        "suggestion": "Use range(len(items)).",
        "file": "src/app.py",
        "line_start": 2,
        "line_end": None,
    }
    values.update(overrides)
    return ModelFinding(**values)


def model_review(
    *findings: ModelFinding,
    summary: str = "Changes x and adds y.",
    risk_level: str = "low",
    test_suggestions: tuple[ModelTestSuggestion, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ModelReview:
    return ModelReview(
        summary=summary,
        risk_level=risk_level,  # type: ignore[arg-type]
        findings=list(findings),
        test_suggestions=list(test_suggestions),
        limitations=list(limitations),
    )


class FakeReviewModel:
    """Returns canned reviews and records prompts. ``respond`` may inspect the prompt."""

    provider = "fake"
    model = "fake-model"

    def __init__(self, respond: ModelReview | Callable[[ReviewPrompt], ModelReview]) -> None:
        self._respond = respond
        self.prompts: list[ReviewPrompt] = []

    async def review(self, prompt: ReviewPrompt) -> ModelReview:
        self.prompts.append(prompt)
        if isinstance(self._respond, ModelReview):
            return self._respond
        return self._respond(prompt)


def make_builder(
    *, chunk_token_budget: int = 24_000, max_chunks: int = 3, max_file_tokens: int = 8_000
) -> ReviewInputBuilder:
    return ReviewInputBuilder(
        chunk_token_budget=chunk_token_budget,
        max_chunks=max_chunks,
        max_file_tokens=max_file_tokens,
    )


def make_engine(
    model: FakeReviewModel, *, min_confidence: float = 0.3, **builder_options: int
) -> ReviewEngine:
    return ReviewEngine(model, make_builder(**builder_options), min_confidence=min_confidence)


# --- OpenAI Responses API mocking ---------------------------------------------


def responses_api_body(output_text: str | None = None, **overrides: Any) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if output_text is not None:
        content.append({"type": "output_text", "text": output_text, "annotations": []})
    body: dict[str, Any] = {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "model": "gpt-5.6-terra",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "role": "assistant",
                "status": "completed",
                "content": content,
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    body.update(overrides)
    return body


def review_json(**overrides: Any) -> str:
    return json.dumps(model_review().model_dump() | overrides)


def make_openai_model(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_retries: int = 2,
    sleeps: list[float] | None = None,
) -> OpenAIReviewModel:
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    client = AsyncOpenAI(
        api_key="sk-test-sentinel-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return OpenAIReviewModel(
        client,
        model="gpt-5.6-terra",
        max_output_tokens=16_000,
        max_retries=max_retries,
        sleep=fake_sleep,
    )


# --- persistence fakes -----------------------------------------------------------


class InMemoryReviewStore:
    """Mirrors ReviewRepository semantics without a database (see the Postgres tests
    for the real implementation)."""

    def __init__(self) -> None:
        self.rows: list[StoredReview] = []
        self.keys: dict[uuid.UUID, str] = {}
        self.fail_with: Exception | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def get(self, review_id: uuid.UUID) -> StoredReview | None:
        self._check()
        return next((r for r in self.rows if r.id == review_id), None)

    def get_current(self, cache_key: str) -> StoredReview | None:
        self._check()
        return next((r for r in self.rows if r.is_current and self.keys[r.id] == cache_key), None)

    def list(
        self,
        *,
        owner: str | None = None,
        repo: str | None = None,
        pull_number: int | None = None,
        limit: int,
        offset: int,
    ) -> ReviewHistoryPage:
        self._check()
        rows = [
            r
            for r in reversed(self.rows)
            if (owner is None or r.review.pull_request.owner.lower() == owner.lower())
            and (repo is None or r.review.pull_request.repo.lower() == repo.lower())
            and (pull_number is None or r.review.pull_request.number == pull_number)
        ]
        items = [
            ReviewSummary(
                id=r.id,
                owner=r.review.pull_request.owner,
                repo=r.review.pull_request.repo,
                pull_number=r.review.pull_request.number,
                head_sha=r.review.pull_request.head_sha,
                provider="fake",
                model=r.review.model,
                prompt_version=r.review.prompt_version,
                risk_level=r.review.risk_level,
                finding_count=len(r.review.findings),
                is_current=r.is_current,
                created_at=r.created_at,
            )
            for r in rows[offset : offset + limit]
        ]
        return ReviewHistoryPage(items=items, total=len(rows), limit=limit, offset=offset)

    def save(
        self,
        result: ReviewResult,
        *,
        cache_key: str,
        review_config: dict[str, Any],
        provider: str,
        replace_current: bool,
    ) -> StoredReview:
        self._check()
        existing = self.get_current(cache_key)
        if existing is not None and replace_current:
            index = self.rows.index(existing)
            self.rows[index] = existing.model_copy(update={"is_current": False})
        stored = StoredReview(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            is_current=existing is None or replace_current,
            review=result,
        )
        self.rows.append(stored)
        self.keys[stored.id] = cache_key
        return stored


def review_result(
    *, owner: str = "octo-org", repo: str = "widgets", number: int = 42, head_sha: str = "b" * 40,
    **overrides: Any,
) -> ReviewResult:  # fmt: skip
    values: dict[str, Any] = {
        "pull_request": ReviewedPullRequest(
            owner=owner, repo=repo, number=number, head_sha=head_sha
        ),
        "model": "gpt-5.6-terra",
        "prompt_version": "test-prompt",
        "summary": "A stored review.",
        "risk_level": "low",
        "findings": [],
        "test_suggestions": [],
        "reviewed_files": ["src/app.py"],
        "truncated_files": [],
        "skipped_files": [],
        "limitations": [],
    }
    values.update(overrides)
    return ReviewResult(**values)
