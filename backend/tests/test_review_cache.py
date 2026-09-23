"""Cache identity and ReviewService cache behavior (no database: in-memory store)."""

from collections.abc import Callable

import httpx2 as httpx
import pytest

from app.core.config import Settings
from app.db.errors import PersistenceError
from app.services.ai.base import AIConfigurationError
from app.services.ai.config import ReviewConfig, review_cache_key
from app.services.ai.review_engine import ReviewEngine
from app.services.github import GitHubClient, create_http_client
from app.services.reviews import ReviewService
from tests.github_payloads import raw_file, raw_pull_request
from tests.review_helpers import FakeReviewModel, InMemoryReviewStore, make_engine, model_review

CONFIG = ReviewConfig.from_settings(Settings(openai_api_key=None))
KEY_ARGS = {"owner": "octo-org", "repo": "widgets", "pull_number": 42, "head_sha": "b" * 40}


# --- cache identity -----------------------------------------------------------------


def test_cache_key_is_deterministic_and_hex() -> None:
    key = review_cache_key(CONFIG, **KEY_ARGS)

    assert key == review_cache_key(CONFIG, **KEY_ARGS)
    assert len(key) == 64
    int(key, 16)


def test_cache_key_ignores_owner_and_repo_case() -> None:
    upper = {**KEY_ARGS, "owner": "Octo-Org", "repo": "Widgets"}

    assert review_cache_key(CONFIG, **upper) == review_cache_key(CONFIG, **KEY_ARGS)


@pytest.mark.parametrize(
    "change",
    [
        {"head_sha": "c" * 40},
        {"pull_number": 43},
        {"repo": "gadgets"},
        {"owner": "someone-else"},
    ],
)
def test_cache_key_changes_with_pr_identity(change: dict[str, object]) -> None:
    assert review_cache_key(CONFIG, **{**KEY_ARGS, **change}) != review_cache_key(
        CONFIG, **KEY_ARGS
    )


@pytest.mark.parametrize(
    "change",
    [
        {"model": "gpt-other"},
        {"prompt_version": "2099-01-01.1"},
        {"provider": "other"},
        {"chunk_token_budget": 16_000},
        {"max_chunks": 1},
        {"max_file_tokens": 2_000},
        {"min_confidence": 0.5},
    ],
)
def test_cache_key_changes_with_review_config(change: dict[str, object]) -> None:
    other = CONFIG.model_copy(update=change)

    assert review_cache_key(other, **KEY_ARGS) != review_cache_key(CONFIG, **KEY_ARGS)


def test_operational_settings_do_not_affect_cache_identity() -> None:
    tuned = Settings(openai_timeout_seconds=5, openai_max_retries=0, openai_max_output_tokens=2_000)

    assert ReviewConfig.from_settings(tuned) == CONFIG


# --- service behavior ---------------------------------------------------------------


def github_client(head_sha: str = "b" * 40) -> GitHubClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            return httpx.Response(200, json=[raw_file("src/app.py")])
        pr = raw_pull_request()
        pr["head"]["sha"] = head_sha
        return httpx.Response(200, json=pr)

    return GitHubClient(create_http_client(Settings(), transport=httpx.MockTransport(handler)))


class CountingFactory:
    def __init__(self, model: FakeReviewModel | None = None) -> None:
        self.model = model or FakeReviewModel(model_review())
        self.calls = 0

    def __call__(self) -> ReviewEngine:
        self.calls += 1
        return make_engine(self.model)


def service(
    store: InMemoryReviewStore,
    factory: Callable[[], ReviewEngine],
    *,
    head_sha: str = "b" * 40,
    config: ReviewConfig = CONFIG,
) -> ReviewService:
    return ReviewService(github_client(head_sha), store, config, factory)


pytestmark = pytest.mark.anyio


async def test_exact_identity_hits_cache_without_engine() -> None:
    store, factory = InMemoryReviewStore(), CountingFactory()
    first = await service(store, factory).review_pull_request("octo-org", "widgets", 42)

    second = await service(store, factory).review_pull_request("octo-org", "widgets", 42)

    assert (first.cached, second.cached) == (False, True)
    assert second.id == first.id
    assert factory.calls == 1
    assert len(factory.model.prompts) == 1


async def test_different_head_sha_misses() -> None:
    store, factory = InMemoryReviewStore(), CountingFactory()
    await service(store, factory, head_sha="b" * 40).review_pull_request("octo-org", "widgets", 42)

    result = await service(store, factory, head_sha="c" * 40).review_pull_request(
        "octo-org", "widgets", 42
    )

    assert result.cached is False
    assert factory.calls == 2


@pytest.mark.parametrize("change", [{"model": "gpt-other"}, {"prompt_version": "next"}])
async def test_different_config_misses(change: dict[str, str]) -> None:
    store, factory = InMemoryReviewStore(), CountingFactory()
    await service(store, factory).review_pull_request("octo-org", "widgets", 42)

    changed = service(store, factory, config=CONFIG.model_copy(update=change))
    result = await changed.review_pull_request("octo-org", "widgets", 42)

    assert result.cached is False
    assert factory.calls == 2


async def test_force_bypasses_cache_and_keeps_history() -> None:
    store, factory = InMemoryReviewStore(), CountingFactory()
    first = await service(store, factory).review_pull_request("octo-org", "widgets", 42)

    forced = await service(store, factory).review_pull_request(
        "octo-org", "widgets", 42, force=True
    )

    assert forced.cached is False
    assert forced.id != first.id
    assert factory.calls == 2
    assert [r.is_current for r in store.rows] == [False, True]


async def test_engine_factory_not_called_on_cache_hit() -> None:
    store = InMemoryReviewStore()
    await service(store, CountingFactory()).review_pull_request("octo-org", "widgets", 42)

    def unconfigured() -> ReviewEngine:
        raise AIConfigurationError()

    result = await service(store, unconfigured).review_pull_request("octo-org", "widgets", 42)

    assert result.cached is True


async def test_lookup_failure_stops_before_model_call() -> None:
    store, factory = InMemoryReviewStore(), CountingFactory()
    store.fail_with = PersistenceError()

    with pytest.raises(PersistenceError):
        await service(store, factory).review_pull_request("octo-org", "widgets", 42)

    assert factory.calls == 0
