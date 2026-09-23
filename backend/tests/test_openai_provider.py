"""OpenAIReviewModel against the real OpenAI SDK with a mocked HTTP transport."""

import json
from collections.abc import Callable

import httpx2 as httpx
import pytest

from app.core.config import Settings
from app.services.ai.base import (
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
    ReviewPrompt,
)
from app.services.ai.openai_provider import create_openai_client
from tests.review_helpers import make_openai_model, responses_api_body, review_json

PROMPT = ReviewPrompt(instructions="review policy", input="pr context")
Handler = Callable[[httpx.Request], httpx.Response]

pytestmark = pytest.mark.anyio


def ok(output_text: str | None = None, **overrides: object) -> httpx.Response:
    return httpx.Response(200, json=responses_api_body(output_text or review_json(), **overrides))


def error(status: int, code: str | None = None, **headers: str) -> httpx.Response:
    body = {"error": {"message": "upstream said no", "type": "x", "code": code}}
    return httpx.Response(status, json=body, headers=headers)


def sequence(*responses: httpx.Response) -> tuple[Handler, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses[min(len(calls), len(responses)) - 1]

    return handler, calls


async def test_structured_result_is_parsed() -> None:
    output = review_json(
        findings=[
            {
                "category": "bug",
                "severity": "high",
                "confidence": 0.95,
                "title": "t",
                "description": "d",
                "suggestion": "s",
                "file": "a.py",
                "line_start": 3,
                "line_end": None,
            }
        ]
    )
    handler, calls = sequence(ok(output))

    review = await make_openai_model(handler).review(PROMPT)

    assert review.findings[0].confidence == 0.95
    body = json.loads(calls[0].content)
    assert body["model"] == "gpt-5.6-terra"
    assert body["instructions"] == "review policy"
    assert body["input"] == "pr context"
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert calls[0].url.path.endswith("/responses")


@pytest.mark.parametrize(
    "output_text",
    [
        "not json at all",
        review_json(risk_level="catastrophic"),
        review_json(
            findings=[
                {
                    "category": "bug",
                    "severity": "high",
                    "confidence": 1.7,
                    "title": "t",
                    "description": "d",
                    "suggestion": "s",
                    "file": None,
                    "line_start": None,
                    "line_end": None,
                }
            ]
        ),
        json.dumps({"summary": "missing everything else"}),
    ],
)
async def test_invalid_structured_output_raises_response_error(output_text: str) -> None:
    handler, _ = sequence(ok(output_text))

    with pytest.raises(AIResponseError):
        await make_openai_model(handler).review(PROMPT)


async def test_refusal_raises_response_error() -> None:
    body = responses_api_body()
    body["output"][0]["content"] = [{"type": "refusal", "refusal": "I can't help with that."}]
    handler, _ = sequence(httpx.Response(200, json=body))

    with pytest.raises(AIResponseError, match="declined"):
        await make_openai_model(handler).review(PROMPT)


async def test_empty_output_raises_response_error() -> None:
    handler, _ = sequence(httpx.Response(200, json=responses_api_body(output=[])))

    with pytest.raises(AIResponseError):
        await make_openai_model(handler).review(PROMPT)


async def test_incomplete_response_raises_response_error() -> None:
    handler, _ = sequence(
        ok(
            '{"summary": "cut',
            status="incomplete",
            incomplete_details={"reason": "max_output_tokens"},
        )
    )

    with pytest.raises(AIResponseError):
        await make_openai_model(handler).review(PROMPT)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (error(401, "invalid_api_key"), AIConfigurationError),
        (error(403), AIConfigurationError),
        (error(404, "model_not_found"), AIConfigurationError),
        (error(400, "invalid_request_error"), AIConfigurationError),
        (error(429, "insufficient_quota"), AIConfigurationError),
        (error(409), AIResponseError),
    ],
)
async def test_non_retryable_errors_fail_immediately(
    response: httpx.Response, expected: type[AIProviderError]
) -> None:
    handler, calls = sequence(response)

    with pytest.raises(expected):
        await make_openai_model(handler).review(PROMPT)

    assert len(calls) == 1


async def test_rate_limit_retries_then_fails() -> None:
    handler, calls = sequence(error(429, "rate_limit_exceeded"))
    sleeps: list[float] = []

    with pytest.raises(AIRateLimitError):
        await make_openai_model(handler, max_retries=2, sleeps=sleeps).review(PROMPT)

    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


async def test_rate_limit_honours_short_retry_after() -> None:
    handler, calls = sequence(error(429, **{"retry-after": "3"}), ok())
    sleeps: list[float] = []

    await make_openai_model(handler, sleeps=sleeps).review(PROMPT)

    assert len(calls) == 2
    assert sleeps == [3.0]


async def test_rate_limit_with_long_retry_after_is_not_retried() -> None:
    handler, calls = sequence(error(429, **{"retry-after": "120"}))

    with pytest.raises(AIRateLimitError) as exc_info:
        await make_openai_model(handler).review(PROMPT)

    assert len(calls) == 1
    assert exc_info.value.retry_after == 120


async def test_server_error_is_retried_and_can_recover() -> None:
    handler, calls = sequence(error(500), error(503), ok())

    review = await make_openai_model(handler).review(PROMPT)

    assert review.summary
    assert len(calls) == 3


async def test_persistent_server_error_raises_unavailable() -> None:
    handler, calls = sequence(error(502))

    with pytest.raises(AIUnavailableError):
        await make_openai_model(handler, max_retries=1).review(PROMPT)

    assert len(calls) == 2


async def test_connection_error_is_retried() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return ok()

    await make_openai_model(handler).review(PROMPT)

    assert len(calls) == 2


async def test_timeout_is_not_retried() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AITimeoutError):
        await make_openai_model(handler).review(PROMPT)

    assert len(calls) == 1


async def test_error_messages_do_not_leak_key_or_upstream_payload() -> None:
    handler, _ = sequence(error(401, "invalid_api_key"))

    with pytest.raises(AIProviderError) as exc_info:
        await make_openai_model(handler).review(PROMPT)

    assert "sk-test-sentinel-key" not in exc_info.value.message
    assert "upstream said no" not in exc_info.value.message


def test_no_api_key_means_no_client() -> None:
    assert create_openai_client(Settings(openai_api_key=None)) is None
    assert create_openai_client(Settings(openai_api_key="   ")) is None


def test_api_key_hidden_from_settings_repr() -> None:
    assert "sk-real-looking" not in repr(Settings(openai_api_key="sk-real-looking"))
