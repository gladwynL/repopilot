"""PostgreSQL storage for completed reviews."""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, raiseload

from app.db.errors import translate_db_errors
from app.models.review import ReviewFindingRecord, ReviewRecord, ReviewTestSuggestionRecord
from app.schemas.review import (
    ReviewedPullRequest,
    ReviewFinding,
    ReviewHistoryPage,
    ReviewResult,
    ReviewSummary,
    SkippedFile,
    StoredReview,
    TestSuggestion,
)

logger = logging.getLogger(__name__)


class ReviewRepository:
    """Stores reviews. Every public method ends its transaction before returning, so no
    connection is left idle in a transaction while the caller awaits GitHub or a model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, review_id: uuid.UUID) -> StoredReview | None:
        with translate_db_errors(self._session):
            record = self._session.get(ReviewRecord, review_id)
            stored = _to_stored(record) if record else None
            self._session.commit()
            return stored

    def get_current(self, cache_key: str) -> StoredReview | None:
        with translate_db_errors(self._session):
            stored = self._current(cache_key)
            self._session.commit()
            return stored

    def list(
        self,
        *,
        owner: str | None = None,
        repo: str | None = None,
        pull_number: int | None = None,
        limit: int,
        offset: int,
    ) -> ReviewHistoryPage:
        filters = []
        if owner is not None:
            filters.append(func.lower(ReviewRecord.owner) == owner.lower())
        if repo is not None:
            filters.append(func.lower(ReviewRecord.repo) == repo.lower())
        if pull_number is not None:
            filters.append(ReviewRecord.pull_number == pull_number)

        with translate_db_errors(self._session):
            total = self._session.scalar(
                select(func.count()).select_from(ReviewRecord).where(*filters)
            )
            records = self._session.scalars(
                select(ReviewRecord)
                .where(*filters)
                # id breaks ties so pages are stable when timestamps collide.
                .order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
                .limit(limit)
                .offset(offset)
                .options(raiseload(ReviewRecord.findings), raiseload(ReviewRecord.test_suggestions))
            ).all()
            page = ReviewHistoryPage(
                items=[_to_summary(r) for r in records],
                total=total or 0,
                limit=limit,
                offset=offset,
            )
            self._session.commit()
            return page

    def save(
        self,
        result: ReviewResult,
        *,
        cache_key: str,
        review_config: dict[str, Any],
        provider: str,
        replace_current: bool,
    ) -> StoredReview:
        """Persist a review with its findings and test suggestions in one transaction.

        Saves for the same ``cache_key`` are serialized with a transaction-scoped advisory
        lock, so deciding which review is current cannot race:

        - ``replace_current`` (forced re-run): the previous current review is demoted and
          stays in history; the new review becomes current.
        - otherwise: the new review becomes current only if none exists. If a concurrent
          request stored one first, the new review is kept as history and the earlier one
          stays current.

        The partial unique index on ``cache_key WHERE is_current`` remains the final
        guarantee; if it is ever violated anyway, the save fails as a ``PersistenceError``.
        """
        with translate_db_errors(self._session):
            self._session.execute(
                select(func.pg_advisory_xact_lock(func.hashtextextended(cache_key, 0)))
            )
            if replace_current:
                self._session.execute(
                    update(ReviewRecord)
                    .where(ReviewRecord.cache_key == cache_key, ReviewRecord.is_current)
                    .values(is_current=False)
                )
                is_current = True
            else:
                is_current = self._current(cache_key) is None
                if not is_current:
                    logger.info("review.cache_race cache_key=%s kept_as_history=true", cache_key)
            record = _to_record(result, cache_key, review_config, provider, is_current)
            self._session.add(record)
            self._session.flush()
            stored = _to_stored(record)
            self._session.commit()  # also releases the advisory lock
            return stored

    def _current(self, cache_key: str) -> StoredReview | None:
        record = self._session.scalars(
            select(ReviewRecord).where(ReviewRecord.cache_key == cache_key, ReviewRecord.is_current)
        ).one_or_none()
        return _to_stored(record) if record else None


def _to_record(
    result: ReviewResult,
    cache_key: str,
    review_config: dict[str, Any],
    provider: str,
    is_current: bool,
) -> ReviewRecord:
    pr = result.pull_request
    return ReviewRecord(
        id=uuid.uuid4(),
        cache_key=cache_key,
        is_current=is_current,
        owner=pr.owner,
        repo=pr.repo,
        pull_number=pr.number,
        head_sha=pr.head_sha,
        provider=provider,
        model=result.model,
        prompt_version=result.prompt_version,
        review_config=review_config,
        summary=result.summary,
        risk_level=result.risk_level,
        finding_count=len(result.findings),
        reviewed_files=list(result.reviewed_files),
        truncated_files=list(result.truncated_files),
        skipped_files=[s.model_dump() for s in result.skipped_files],
        limitations=list(result.limitations),
        findings=[
            ReviewFindingRecord(position=i, **f.model_dump()) for i, f in enumerate(result.findings)
        ],
        test_suggestions=[
            ReviewTestSuggestionRecord(position=i, **s.model_dump())
            for i, s in enumerate(result.test_suggestions)
        ],
    )


def _to_stored(record: ReviewRecord) -> StoredReview:
    return StoredReview(
        id=record.id,
        created_at=record.created_at,
        is_current=record.is_current,
        review=ReviewResult(
            pull_request=ReviewedPullRequest(
                owner=record.owner,
                repo=record.repo,
                number=record.pull_number,
                head_sha=record.head_sha,
            ),
            model=record.model,
            prompt_version=record.prompt_version,
            summary=record.summary,
            risk_level=record.risk_level,  # type: ignore[arg-type]
            findings=[
                ReviewFinding.model_validate(f, from_attributes=True) for f in record.findings
            ],
            test_suggestions=[
                TestSuggestion.model_validate(s, from_attributes=True)
                for s in record.test_suggestions
            ],
            reviewed_files=record.reviewed_files,
            truncated_files=record.truncated_files,
            skipped_files=[SkippedFile.model_validate(s) for s in record.skipped_files],
            limitations=record.limitations,
        ),
    )


def _to_summary(record: ReviewRecord) -> ReviewSummary:
    return ReviewSummary.model_validate(record, from_attributes=True)
