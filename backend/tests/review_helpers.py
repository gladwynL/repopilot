"""Builders and fakes shared by the review-engine tests. No network or paid API calls."""

import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
from openai import AsyncOpenAI

from app.schemas.pull_request import PullRequest, PullRequestFile
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
