from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.review import ReviewResult

ConditionKind = Literal[
    "detects_expected_bug",
    "finding_limit",
    "suggests_test",
    "acknowledges_limitation",
    "no_unreviewable_references",
]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ConditionResult(_Frozen):
    kind: ConditionKind
    passed: bool
    detail: str


class EvaluationCaseResult(_Frozen):
    case_id: str
    description: str
    passed: bool
    conditions: list[ConditionResult]
    """Empty when the case errored before a review was produced."""
    error: str | None
    """Sanitized RepoPilot error message when the provider failed."""
    latency_ms: int | None
    review: ReviewResult | None

    @property
    def failed_expectations(self) -> list[str]:
        return [c.detail for c in self.conditions if not c.passed]


class ConditionMetric(_Frozen):
    evaluated: int
    passed: int
    rate: float | None


class EvaluationMetrics(_Frozen):
    case_pass_rate: float | None
    """Passed cases / total cases; errored cases count as not passed."""
    conditions: dict[str, ConditionMetric]
    """Pass rate per condition kind, over cases that produced a review and define it."""


class EvaluationRunResult(_Frozen):
    id: UUID
    provider: str
    model: str
    prompt_version: str
    review_config: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    """Cases that produced a review but missed at least one expectation."""
    errored_cases: int
    """Cases where the provider failed, so expectations could not be checked."""
    metrics: EvaluationMetrics
    cases: list[EvaluationCaseResult]
