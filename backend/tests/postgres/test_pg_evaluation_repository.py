import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.evaluations import EvaluationRepository
from app.services.ai.base import AIConfigurationError, ModelReview, ReviewPrompt
from app.services.ai.config import ReviewConfig
from app.services.evaluation.cases import CLEAN_CHANGE, OBVIOUS_BUG
from app.services.evaluation.runner import EvaluationRunner
from tests.review_helpers import FakeReviewModel, make_engine, model_review

pytestmark = pytest.mark.anyio

CONFIG = ReviewConfig.from_settings(Settings(openai_api_key=None))


def fixed_runner(model: FakeReviewModel) -> EvaluationRunner:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    return EvaluationRunner(make_engine(model), CONFIG, now=lambda: now, clock=lambda: 0.0)


async def test_run_round_trips_through_postgres(session: Session) -> None:
    run = await fixed_runner(FakeReviewModel(model_review())).run([CLEAN_CHANGE, OBVIOUS_BUG])

    EvaluationRepository(session).save(run)
    loaded = EvaluationRepository(session).get(run.id)

    assert loaded == run
    assert (loaded.passed_cases, loaded.failed_cases) == (1, 1)


async def test_errored_cases_store_only_sanitized_messages(session: Session) -> None:
    def fail(_: ReviewPrompt) -> ModelReview:
        raise AIConfigurationError("The AI provider rejected the configured credentials.")

    run = await fixed_runner(FakeReviewModel(fail)).run([CLEAN_CHANGE])
    EvaluationRepository(session).save(run)

    rows = session.execute(text("SELECT error, details FROM evaluation_case_results")).all()
    (error, details) = rows[0]
    assert error == "The AI provider rejected the configured credentials."
    stored = json.dumps(details) + (error or "")
    for forbidden in ("sk-", "Bearer", "Authorization"):
        assert forbidden not in stored
