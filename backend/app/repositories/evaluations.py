"""PostgreSQL storage for evaluation runs."""

import uuid

from sqlalchemy.orm import Session

from app.db.errors import translate_db_errors
from app.models.evaluation import EvaluationCaseResultRecord, EvaluationRunRecord
from app.services.evaluation.schemas import (
    ConditionResult,
    EvaluationCaseResult,
    EvaluationMetrics,
    EvaluationRunResult,
)


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: EvaluationRunResult) -> None:
        """Persist a run and all its case results in one transaction."""
        with translate_db_errors(self._session):
            self._session.add(_to_record(run))
            self._session.commit()

    def get(self, run_id: uuid.UUID) -> EvaluationRunResult | None:
        with translate_db_errors(self._session):
            record = self._session.get(EvaluationRunRecord, run_id)
            return _to_result(record) if record else None


def _to_record(run: EvaluationRunResult) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        id=run.id,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        review_config=run.review_config,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_cases=run.total_cases,
        passed_cases=run.passed_cases,
        failed_cases=run.failed_cases,
        errored_cases=run.errored_cases,
        metrics=run.metrics.model_dump(mode="json"),
        cases=[
            EvaluationCaseResultRecord(
                position=i,
                case_id=case.case_id,
                passed=case.passed,
                error=case.error,
                latency_ms=case.latency_ms,
                details={
                    "description": case.description,
                    "conditions": [c.model_dump(mode="json") for c in case.conditions],
                    "review": case.review.model_dump(mode="json") if case.review else None,
                },
            )
            for i, case in enumerate(run.cases)
        ],
    )


def _to_result(record: EvaluationRunRecord) -> EvaluationRunResult:
    return EvaluationRunResult(
        id=record.id,
        provider=record.provider,
        model=record.model,
        prompt_version=record.prompt_version,
        review_config=record.review_config,
        started_at=record.started_at,
        completed_at=record.completed_at,
        total_cases=record.total_cases,
        passed_cases=record.passed_cases,
        failed_cases=record.failed_cases,
        errored_cases=record.errored_cases,
        metrics=EvaluationMetrics.model_validate(record.metrics),
        cases=[
            EvaluationCaseResult(
                case_id=case.case_id,
                description=case.details["description"],
                passed=case.passed,
                conditions=[ConditionResult.model_validate(c) for c in case.details["conditions"]],
                error=case.error,
                latency_ms=case.latency_ms,
                review=case.details["review"],
            )
            for case in record.cases
        ],
    )
