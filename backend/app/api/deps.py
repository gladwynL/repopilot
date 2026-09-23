from fastapi import Request

from app.core.config import Settings
from app.services.ai.base import AIConfigurationError
from app.services.ai.input_builder import ReviewInputBuilder
from app.services.ai.openai_provider import OpenAIReviewModel
from app.services.ai.review_engine import ReviewEngine
from app.services.github import GitHubClient


def get_github_client(request: Request) -> GitHubClient:
    return GitHubClient(request.app.state.github_http)


def get_review_engine(request: Request) -> ReviewEngine:
    settings: Settings = request.app.state.settings
    openai_client = request.app.state.openai_client
    if openai_client is None:
        raise AIConfigurationError("AI review is not configured on this server.")
    model = OpenAIReviewModel(
        openai_client,
        model=settings.openai_model,
        max_output_tokens=settings.openai_max_output_tokens,
        max_retries=settings.openai_max_retries,
    )
    input_builder = ReviewInputBuilder(
        chunk_token_budget=settings.review_chunk_token_budget,
        max_chunks=settings.review_max_chunks,
        max_file_tokens=settings.review_max_file_tokens,
    )
    return ReviewEngine(model, input_builder, min_confidence=settings.review_min_confidence)
