from app.schemas.review import ReviewResult
from app.services.evaluation.cases import Expectations
from app.services.evaluation.schemas import (
    ConditionMetric,
    ConditionResult,
    EvaluationCaseResult,
    EvaluationMetrics,
)

HIGH_CONFIDENCE = 0.8


def evaluate_conditions(result: ReviewResult, expected: Expectations) -> list[ConditionResult]:
    """Check a review against a case's expectations; only defined expectations are checked."""
    conditions: list[ConditionResult] = []

    if expected.min_high_confidence_bugs:
        strong = [
            f for f in result.findings if f.category == "bug" and f.confidence >= HIGH_CONFIDENCE
        ]
        conditions.append(
            ConditionResult(
                kind="detects_expected_bug",
                passed=len(strong) >= expected.min_high_confidence_bugs,
                detail=f"expected >= {expected.min_high_confidence_bugs} bug finding(s) with "
                f"confidence >= {HIGH_CONFIDENCE}, got {len(strong)}",
            )
        )
    if expected.max_findings is not None:
        conditions.append(
            ConditionResult(
                kind="finding_limit",
                passed=len(result.findings) <= expected.max_findings,
                detail=(
                    f"expected <= {expected.max_findings} finding(s), got {len(result.findings)}"
                ),
            )
        )
    if expected.requires_test_suggestion:
        conditions.append(
            ConditionResult(
                kind="suggests_test",
                passed=bool(result.test_suggestions),
                detail=f"expected a test suggestion, got {len(result.test_suggestions)}",
            )
        )
    for text in expected.limitation_mentions:
        conditions.append(
            ConditionResult(
                kind="acknowledges_limitation",
                passed=any(text in limitation for limitation in result.limitations),
                detail=f"expected a limitation mentioning {text!r}",
            )
        )
    for name in expected.unreviewable_files:
        offending = sum(1 for f in result.findings if f.file == name)
        conditions.append(
            ConditionResult(
                kind="no_unreviewable_references",
                passed=offending == 0,
                detail=f"expected no findings on unreviewable file {name!r}, got {offending}",
            )
        )
    return conditions


def aggregate_metrics(cases: list[EvaluationCaseResult]) -> EvaluationMetrics:
    counts: dict[str, list[int]] = {}
    for case in cases:
        for condition in case.conditions:
            evaluated_passed = counts.setdefault(condition.kind, [0, 0])
            evaluated_passed[0] += 1
            evaluated_passed[1] += int(condition.passed)
    return EvaluationMetrics(
        case_pass_rate=_rate(sum(c.passed for c in cases), len(cases)),
        conditions={
            kind: ConditionMetric(evaluated=evaluated, passed=passed, rate=_rate(passed, evaluated))
            for kind, (evaluated, passed) in sorted(counts.items())
        },
    )


def _rate(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None
