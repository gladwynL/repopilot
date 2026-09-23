import logging
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.services.ai.base import AIProviderError
from app.services.ai.config import ReviewConfig
from app.services.ai.review_engine import ReviewEngine
from app.services.evaluation.cases import EvalCase
from app.services.evaluation.checks import aggregate_metrics, evaluate_conditions
from app.services.evaluation.schemas import EvaluationCaseResult, EvaluationRunResult

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Runs evaluation cases through a review engine and scores them against expectations."""

    def __init__(
        self,
        engine: ReviewEngine,
        config: ReviewConfig,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._engine = engine
        self._config = config
        self._now = now
        self._clock = clock

    async def run(self, cases: Sequence[EvalCase]) -> EvaluationRunResult:
        started_at = self._now()
        # Sequential on purpose: live runs stay cheap and easy on provider rate limits.
        results = [await self._run_case(case) for case in cases]
        errored = sum(r.error is not None for r in results)
        passed = sum(r.passed for r in results)
        run = EvaluationRunResult(
            id=uuid.uuid4(),
            provider=self._config.provider,
            model=self._config.model,
            prompt_version=self._config.prompt_version,
            review_config=self._config.model_dump(),
            started_at=started_at,
            completed_at=self._now(),
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=len(results) - passed - errored,
            errored_cases=errored,
            metrics=aggregate_metrics(results),
            cases=results,
        )
        logger.info(
            "evaluation.completed run_id=%s model=%s prompt_version=%s total=%d passed=%d "
            "failed=%d errored=%d",
            run.id, run.model, run.prompt_version, run.total_cases, run.passed_cases,
            run.failed_cases, run.errored_cases,
        )  # fmt: skip
        return run

    async def _run_case(self, case: EvalCase) -> EvaluationCaseResult:
        started = self._clock()
        try:
            review = await self._engine.review_pull_request(case.pr)
        except AIProviderError as exc:
            return EvaluationCaseResult(
                case_id=case.id,
                description=case.description,
                passed=False,
                conditions=[],
                error=exc.message,
                latency_ms=self._elapsed_ms(started),
                review=None,
            )
        conditions = evaluate_conditions(review, case.expectations)
        return EvaluationCaseResult(
            case_id=case.id,
            description=case.description,
            passed=all(c.passed for c in conditions),
            conditions=conditions,
            error=None,
            latency_ms=self._elapsed_ms(started),
            review=review,
        )

    def _elapsed_ms(self, started: float) -> int:
        return round((self._clock() - started) * 1000)
