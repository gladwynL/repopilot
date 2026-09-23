"""OpenAI implementation of ``ReviewModel`` using the Responses API with structured outputs."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import openai
from openai import AsyncOpenAI
from openai.types.responses import ParsedResponse
from pydantic import ValidationError

from app.core.config import Settings
from app.services.ai.base import (
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
    ModelReview,
    ReviewPrompt,
)

logger = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 1.0
MAX_RETRY_WAIT_SECONDS = 20


def create_openai_client(settings: Settings) -> AsyncOpenAI | None:
    """Returns ``None`` when no API key is configured; reviews then fail with a 503."""
    if settings.openai_api_key is None:
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=0,  # retries are handled by OpenAIReviewModel so the policy is explicit
    )


class OpenAIReviewModel:
    provider = "openai"

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str,
        max_output_tokens: int,
        max_retries: int,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._max_retries = max_retries
        self._sleep = sleep

    async def review(self, prompt: ReviewPrompt) -> ModelReview:
        attempt = 0
        while True:
            try:
                return await self._review_once(prompt)
            except (AIRateLimitError, AIUnavailableError) as exc:
                delay = self._retry_delay(exc, attempt)
                if delay is None:
                    raise
                attempt += 1
                logger.warning(
                    "ai.retry provider=%s model=%s attempt=%d error=%s delay_s=%.1f",
                    self.provider, self.model, attempt, type(exc).__name__, delay,
                )  # fmt: skip
                await self._sleep(delay)

    def _retry_delay(self, exc: AIProviderError, attempt: int) -> float | None:
        """Seconds to wait before retrying, or ``None`` if the error should not be retried."""
        if attempt >= self._max_retries or isinstance(exc, AITimeoutError):
            # A timed-out request already cost the full timeout; retrying multiplies latency.
            return None
        if isinstance(exc, AIRateLimitError) and exc.retry_after is not None:
            return float(exc.retry_after) if exc.retry_after <= MAX_RETRY_WAIT_SECONDS else None
        return BACKOFF_BASE_SECONDS * 2**attempt

    async def _review_once(self, prompt: ReviewPrompt) -> ModelReview:
        try:
            response = await self._client.responses.parse(
                model=self.model,
                instructions=prompt.instructions,
                input=prompt.input,
                text_format=ModelReview,
                max_output_tokens=self._max_output_tokens,
                store=False,
            )
        except ValidationError as exc:  # output text did not match the schema
            raise AIResponseError() from exc
        except openai.OpenAIError as exc:
            raise _translate_error(exc) from exc
        return _extract_review(response)


def _extract_review(response: ParsedResponse[ModelReview]) -> ModelReview:
    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else None
        logger.warning("ai.incomplete_response reason=%s", reason)
        raise AIResponseError("The AI provider stopped before completing the review.")
    parsed = response.output_parsed
    if parsed is not None:
        return parsed
    if any(
        getattr(content, "type", None) == "refusal"
        for item in response.output
        if item.type == "message"
        for content in item.content
    ):
        raise AIResponseError("The AI provider declined to review this pull request.")
    raise AIResponseError()


def _translate_error(exc: openai.OpenAIError) -> AIProviderError:
    # APITimeoutError subclasses APIConnectionError, so it must be checked first.
    if isinstance(exc, openai.APITimeoutError):
        return AITimeoutError()
    if isinstance(exc, openai.APIConnectionError):
        return AIUnavailableError()
    if isinstance(exc, openai.RateLimitError):
        if exc.code == "insufficient_quota":
            return AIConfigurationError("The AI provider account has no remaining quota.")
        return AIRateLimitError(retry_after=_retry_after(exc))
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return AIConfigurationError("The AI provider rejected the configured credentials.")
    if isinstance(exc, openai.BadRequestError | openai.NotFoundError):
        # e.g. unknown model or a request the provider refuses to accept as configured.
        return AIConfigurationError("The AI provider rejected the review request.")
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return AIUnavailableError()
    return AIResponseError()


def _retry_after(exc: openai.APIStatusError) -> int | None:
    value = exc.response.headers.get("retry-after", "")
    return int(value) if value.isdigit() else None
