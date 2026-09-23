from openai import AsyncOpenAI

from app.core.config import Settings
from app.services.ai.config import ReviewConfig
from app.services.ai.input_builder import ReviewInputBuilder
from app.services.ai.openai_provider import OpenAIReviewModel
from app.services.ai.review_engine import ReviewEngine


def create_review_engine(settings: Settings, client: AsyncOpenAI) -> ReviewEngine:
    """Build the production review engine (OpenAI provider) from settings."""
    config = ReviewConfig.from_settings(settings)
    model = OpenAIReviewModel(
        client,
        model=config.model,
        max_output_tokens=settings.openai_max_output_tokens,
        max_retries=settings.openai_max_retries,
    )
    input_builder = ReviewInputBuilder(
        chunk_token_budget=config.chunk_token_budget,
        max_chunks=config.max_chunks,
        max_file_tokens=config.max_file_tokens,
    )
    return ReviewEngine(model, input_builder, min_confidence=config.min_confidence)
