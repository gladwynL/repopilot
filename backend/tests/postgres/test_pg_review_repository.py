import threading
import uuid
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.errors import PersistenceError
from app.db.session import create_db_engine, create_session_factory
from app.models.review import ReviewFindingRecord, ReviewRecord, ReviewTestSuggestionRecord
from app.repositories.reviews import ReviewRepository, _to_record
from app.schemas.review import ReviewFinding, SkippedFile, TestSuggestion
from tests.review_helpers import review_result

CONFIG: dict[str, Any] = {"provider": "openai", "model": "gpt-5.6-terra"}


def save(
    repository: ReviewRepository, key: str = "k" * 64, *, force: bool = False, **result: Any
) -> Any:
    return repository.save(
        review_result(**result),
        cache_key=key,
        review_config=CONFIG,
        provider="openai",
        replace_current=force,
    )


def rich_result() -> dict[str, Any]:
    return {
        "risk_level": "high",
        "findings": [
            ReviewFinding(
                category="bug",
                severity="high",
                confidence=0.9,
                title="First",
                description="d1",
                suggestion="s1",
                file="src/app.py",
                line_start=3,
                line_end=5,
            ),
            ReviewFinding(
                category="security",
                severity="medium",
                confidence=0.6,
                title="Second",
                description="d2",
                suggestion="s2",
                file=None,
            ),
        ],
        "test_suggestions": [
            TestSuggestion(description="Test the boundary", file="tests/test_app.py"),
            TestSuggestion(description="Test errors", file=None),
        ],
        "reviewed_files": ["src/app.py", "src/util.py"],
        "truncated_files": ["src/util.py"],
        "skipped_files": [SkippedFile(filename="logo.png", reason="no_patch")],
        "limitations": ["GitHub provided no diff for logo.png."],
    }


def test_save_round_trips_full_review(session: Session) -> None:
    repo = ReviewRepository(session)
    original = review_result(**rich_result())

    stored = repo.save(
        original, cache_key="a" * 64, review_config=CONFIG, provider="openai", replace_current=False
    )

    assert stored.is_current is True
    assert stored.created_at.tzinfo is not None
    fetched = ReviewRepository(session).get(stored.id)
    assert fetched is not None
    assert fetched.review == original
    record = session.get(ReviewRecord, stored.id)
    assert record is not None
    assert record.finding_count == 2
    assert record.review_config == CONFIG


def test_get_unknown_id_returns_none(session: Session) -> None:
    assert ReviewRepository(session).get(uuid.uuid4()) is None


def test_get_current_matches_only_exact_key(session: Session) -> None:
    repo = ReviewRepository(session)
    stored = save(repo, "a" * 64)

    assert repo.get_current("a" * 64) == stored
    assert repo.get_current("b" * 64) is None


def test_forced_save_demotes_previous_current(session: Session) -> None:
    repo = ReviewRepository(session)
    first = save(repo, summary="first")

    second = save(repo, force=True, summary="second")

    assert repo.get_current("k" * 64) == second
    old = repo.get(first.id)
    assert old is not None and old.is_current is False
    assert repo.list(limit=10, offset=0).total == 2


def test_unforced_save_never_replaces_existing_current(session: Session) -> None:
    repo = ReviewRepository(session)
    first = save(repo, summary="first")

    late = save(repo, summary="lost the race")

    assert late.is_current is False
    assert repo.get_current("k" * 64) == first


def test_database_rejects_two_current_rows_for_one_key(session: Session) -> None:
    for _ in range(2):
        session.add(_to_record(review_result(), "k" * 64, CONFIG, "openai", is_current=True))
    with pytest.raises(IntegrityError, match="uq_reviews_current_cache_key"):
        session.commit()


def test_failed_save_rolls_back_everything(session: Session) -> None:
    bad = ReviewFinding.model_construct(
        category="bug",
        severity="high",
        confidence=1.5,  # violates the database CHECK constraint
        title="t",
        description="d",
        suggestion="s",
        file=None,
        line_start=None,
        line_end=None,
    )
    result = review_result().model_copy(update={"findings": [bad]})

    with pytest.raises(PersistenceError) as exc_info:
        ReviewRepository(session).save(
            result,
            cache_key="k" * 64,
            review_config=CONFIG,
            provider="openai",
            replace_current=False,
        )

    assert "confidence" not in exc_info.value.message
    for model in (ReviewRecord, ReviewFindingRecord, ReviewTestSuggestionRecord):
        assert session.scalar(select(func.count()).select_from(model)) == 0


def test_history_newest_first_with_filters_and_pagination(session: Session) -> None:
    repo = ReviewRepository(session)
    ids = []
    for i, (owner, repo_name, number) in enumerate(
        [("octo-org", "widgets", 1), ("octo-org", "widgets", 2), ("Other", "gadgets", 1)]
    ):
        stored = save(repo, f"{i}" * 64, owner=owner, repo=repo_name, number=number)
        ids.append(stored.id)
        # Distinct, increasing timestamps (now() is per-transaction and could tie).
        session.execute(
            text("UPDATE reviews SET created_at = now() + make_interval(secs => :s) WHERE id = :i"),
            {"s": i, "i": stored.id},
        )
        session.commit()

    everything = repo.list(limit=10, offset=0)
    assert [item.id for item in everything.items] == list(reversed(ids))
    assert everything.total == 3

    widgets = repo.list(owner="OCTO-ORG", repo="Widgets", limit=10, offset=0)
    assert [item.pull_number for item in widgets.items] == [2, 1]
    assert repo.list(owner="octo-org", pull_number=2, limit=10, offset=0).total == 1

    page = repo.list(limit=1, offset=1)
    assert ([item.id for item in page.items], page.total) == ([ids[1]], 3)
    assert page.items[0].finding_count == 0


def run_concurrently(factory: sessionmaker[Session], count: int, *, force: bool) -> list[Any]:
    barrier = threading.Barrier(count)
    results: list[Any] = []
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        with factory() as session:
            barrier.wait()
            try:
                results.append(save(ReviewRepository(session), force=force, summary=f"run {i}"))
            except BaseException as exc:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    return results


@pytest.mark.parametrize("force", [False, True])
def test_concurrent_saves_keep_exactly_one_current(
    session_factory: sessionmaker[Session], pg_engine: Engine, force: bool
) -> None:
    results = run_concurrently(session_factory, 6, force=force)

    assert len(results) == 6
    with session_factory() as session:
        current = session.scalars(
            select(ReviewRecord).where(ReviewRecord.cache_key == "k" * 64, ReviewRecord.is_current)
        ).all()
        total = session.scalar(select(func.count()).select_from(ReviewRecord))
    assert len(current) == 1
    assert total == 6


def test_unreachable_database_raises_safe_persistence_error() -> None:
    url = "postgresql+psycopg://nobody:secret-db-password@127.0.0.1:1/nothing_test"
    engine = create_db_engine(url)
    try:
        with create_session_factory(engine)() as session, pytest.raises(PersistenceError) as exc:
            ReviewRepository(session).get_current("k" * 64)
    finally:
        engine.dispose()

    assert exc.value.message == "Review storage is unavailable."
    assert "secret-db-password" not in str(exc.value)
