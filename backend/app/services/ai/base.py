"""Provider-neutral contract between the review engine and an LLM provider.

``ModelReview`` is the structured output a provider must return. It is deliberately
separate from the public ``ReviewResult``: the engine validates and post-processes it
(line checks, confidence floor, deduplication) before anything reaches the API.
"""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import FindingCategory, RiskLevel, Severity


class _ModelOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModelFinding(_ModelOutput):
    category: FindingCategory
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    suggestion: str
    file: str | None
    line_start: int | None = Field(ge=1)
    line_end: int | None = Field(ge=1)


class ModelTestSuggestion(_ModelOutput):
    __test__ = False  # not a pytest test class

    description: str
    file: str | None


class ModelReview(_ModelOutput):
    summary: str
    risk_level: RiskLevel
    findings: list[ModelFinding]
    test_suggestions: list[ModelTestSuggestion]
    limitations: list[str]


@dataclass(frozen=True)
class ReviewPrompt:
    instructions: str
    input: str


class ReviewModel(Protocol):
    """An LLM that turns a review prompt into a validated ``ModelReview``."""

    provider: str
    model: str

    async def review(self, prompt: ReviewPrompt) -> ModelReview: ...


class AIProviderError(Exception):
    """Base class for LLM provider failures. Messages are safe to show to API clients."""

    message = "The AI provider request failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class AIConfigurationError(AIProviderError):
    message = "AI review is not configured correctly on the server."


class AIRateLimitError(AIProviderError):
    message = "The AI provider is rate limiting requests. Try again later."

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__()
        self.retry_after = retry_after


class AIUnavailableError(AIProviderError):
    message = "The AI provider is unavailable."


class AITimeoutError(AIUnavailableError):
    message = "The AI provider did not respond in time."


class AIResponseError(AIProviderError):
    message = "The AI provider returned an invalid review."
