"""Review orchestration with persistence: GitHub → cache lookup → AI review → storage."""

import asyncio
import logging
from collections.abc import Callable
from functools import partial
from typing import Any, Protocol

from anyio import to_thread

from app.schemas.review import ReviewResult, ReviewRunResponse, StoredReview
from app.services.ai.config import ReviewConfig, review_cache_key
from app.services.ai.review_engine import ReviewEngine
from app.services.github import GitHubClient

logger = logging.getLogger(__name__)


class ReviewCapacityError(Exception):
    """All AI review slots in this process are busy."""

    message = "RepoPilot is already running the maximum number of AI reviews. Try again shortly."
    retry_after = 30


class ReviewStore(Protocol):
    """The subset of ``ReviewRepository`` the service needs (synchronous, run in a thread)."""

    def get_current(self, cache_key: str) -> StoredReview | None: ...

    def save(
        self,
        result: ReviewResult,
        *,
        cache_key: str,
        review_config: dict[str, Any],
        provider: str,
        replace_current: bool,
    ) -> StoredReview: ...


class ReviewService:
    def __init__(
        self,
        github: GitHubClient,
        store: ReviewStore,
        config: ReviewConfig,
        engine_factory: Callable[[], ReviewEngine],
        *,
        review_slots: asyncio.Semaphore | None = None,
    ) -> None:
        """``engine_factory`` is only called on a cache miss, so cached reviews can be
        served even when no AI provider is configured.

        ``review_slots`` caps concurrent AI reviews in this process (not across instances).
        When all slots are busy the request fails fast instead of queueing a long request.
        """
        self._github = github
        self._store = store
        self._config = config
        self._engine_factory = engine_factory
        self._review_slots = review_slots or asyncio.Semaphore(1)

    async def review_pull_request(
        self, owner: str, repo: str, pull_number: int, *, force: bool = False
    ) -> ReviewRunResponse:
        pr = await self._github.get_pull_request(owner, repo, pull_number)
        m = pr.metadata
        cache_key = review_cache_key(
            self._config, owner=m.owner, repo=m.repo, pull_number=m.number, head_sha=m.head.sha
        )
        pr_label = f"{m.owner}/{m.repo}#{m.number}@{m.head.sha[:12]}"

        if not force:
            cached = await to_thread.run_sync(self._store.get_current, cache_key)
            if cached is not None:
                logger.info("review.cache_hit pr=%s review_id=%s", pr_label, cached.id)
                return _response(cached, cached=True)

        logger.info("review.cache_miss pr=%s force=%s", pr_label, force)
        engine = self._engine_factory()
        # No await between the check and the acquire, so this cannot race in one event loop.
        if self._review_slots.locked():
            logger.warning("review.capacity_exceeded pr=%s", pr_label)
            raise ReviewCapacityError()
        async with self._review_slots:
            result = await engine.review_pull_request(pr)
        # The model call is not retried if saving fails, so a storage error never costs a
        # second paid review.
        stored = await to_thread.run_sync(
            partial(
                self._store.save,
                result,
                cache_key=cache_key,
                review_config=self._config.model_dump(),
                provider=self._config.provider,
                replace_current=force,
            )
        )
        return _response(stored, cached=False)


def _response(stored: StoredReview, *, cached: bool) -> ReviewRunResponse:
    return ReviewRunResponse(
        id=stored.id,
        created_at=stored.created_at,
        is_current=stored.is_current,
        review=stored.review,
        cached=cached,
    )
