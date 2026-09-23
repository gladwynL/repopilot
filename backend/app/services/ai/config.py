import hashlib
import json

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.services.ai.prompts import PROMPT_VERSION


class ReviewConfig(BaseModel):
    """Every setting that can change what a review says.

    Two reviews of the same PR commit under equal configs are interchangeable, which is what
    makes caching safe. Operational settings (timeouts, retries, output-token cap) only affect
    whether a review succeeds, not its content, so they are deliberately excluded.
    """

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    prompt_version: str
    chunk_token_budget: int
    max_chunks: int
    max_file_tokens: int
    min_confidence: float

    @classmethod
    def from_settings(cls, settings: Settings, provider: str = "openai") -> "ReviewConfig":
        return cls(
            provider=provider,
            model=settings.openai_model,
            prompt_version=PROMPT_VERSION,
            chunk_token_budget=settings.review_chunk_token_budget,
            max_chunks=settings.review_max_chunks,
            max_file_tokens=settings.review_max_file_tokens,
            min_confidence=settings.review_min_confidence,
        )


def review_cache_key(
    config: ReviewConfig, *, owner: str, repo: str, pull_number: int, head_sha: str
) -> str:
    """SHA-256 over the PR commit identity and the review config, as canonical JSON.

    GitHub owner and repository names are case-insensitive, so they are lowercased.
    """
    identity = {
        "owner": owner.lower(),
        "repo": repo.lower(),
        "pull_number": pull_number,
        "head_sha": head_sha.lower(),
        "config": config.model_dump(),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
