"""Orchestrates a pull request review: input building, model calls, validation, and merging."""

import asyncio
import logging
import re
import time

from app.schemas.pull_request import PullRequest
from app.schemas.review import (
    SEVERITY_RANK,
    ReviewedPullRequest,
    ReviewFinding,
    ReviewResult,
    TestSuggestion,
)
from app.services.ai.base import ModelFinding, ModelReview, ReviewModel
from app.services.ai.input_builder import ReviewInputBuilder
from app.services.ai.prompts import PROMPT_VERSION, build_review_prompt
from app.services.ai.review_input import PreparedFile, ReviewInput

logger = logging.getLogger(__name__)

NOTHING_TO_REVIEW_SUMMARY = (
    "No diff content was available to review, so no AI review was performed."
)


class ReviewEngine:
    def __init__(
        self, model: ReviewModel, input_builder: ReviewInputBuilder, *, min_confidence: float
    ) -> None:
        self._model = model
        self._input_builder = input_builder
        self._min_confidence = min_confidence

    async def review_pull_request(self, pr: PullRequest) -> ReviewResult:
        started = time.perf_counter()
        review_input = self._input_builder.build(pr)
        prompts = [build_review_prompt(review_input, i) for i in range(len(review_input.chunks))]
        # Chunks are independent; any failure fails the whole review rather than
        # returning a silently partial result.
        outputs = await asyncio.gather(*(self._model.review(p) for p in prompts))
        result = self._merge(review_input, list(outputs))

        m = pr.metadata
        logger.info(
            "review.completed provider=%s model=%s prompt_version=%s pr=%s/%s#%d "
            "files_considered=%d files_sent=%d files_skipped=%d truncated=%s chunks=%d "
            "findings=%d duration_ms=%d",
            self._model.provider, self._model.model, PROMPT_VERSION, m.owner, m.repo, m.number,
            review_input.files_considered, len(result.reviewed_files), len(result.skipped_files),
            bool(result.truncated_files or result.skipped_files), len(prompts),
            len(result.findings), (time.perf_counter() - started) * 1000,
        )  # fmt: skip
        return result

    def _merge(self, review_input: ReviewInput, outputs: list[ModelReview]) -> ReviewResult:
        files = {file.filename: file for file in review_input.reviewed_files}
        findings = [
            _ground_finding(raw, files)
            for output in outputs
            for raw in output.findings
            if raw.confidence >= self._min_confidence
        ]
        metadata = review_input.metadata
        return ReviewResult(
            pull_request=ReviewedPullRequest(
                owner=metadata.owner,
                repo=metadata.repo,
                number=metadata.number,
                head_sha=metadata.head.sha,
            ),
            model=self._model.model,
            prompt_version=PROMPT_VERSION,
            summary=_merge_summaries(outputs),
            risk_level=(
                max((o.risk_level for o in outputs), key=SEVERITY_RANK.__getitem__)
                if outputs
                else None
            ),
            findings=sorted(deduplicate_findings(findings), key=_finding_order),
            test_suggestions=_dedupe_test_suggestions(outputs),
            reviewed_files=list(files),
            truncated_files=[name for name, file in files.items() if file.truncated],
            skipped_files=list(review_input.skipped_files),
            limitations=_unique(
                [*review_input.limitations, *(lim for o in outputs for lim in o.limitations)]
            ),
        )


def _ground_finding(raw: ModelFinding, files: dict[str, PreparedFile]) -> ReviewFinding:
    """Keep only references the supplied diff supports; unsupported ones become ``None``."""
    file = files.get(raw.file) if raw.file else None
    line_start, line_end = raw.line_start, raw.line_end
    visible = file.new_lines if file else frozenset()
    if line_start not in visible:
        line_start = line_end = None
    elif line_end is not None and (line_end < line_start or line_end not in visible):
        line_end = None
    return ReviewFinding(
        category=raw.category,
        severity=raw.severity,
        confidence=raw.confidence,
        title=raw.title.strip(),
        description=raw.description.strip(),
        suggestion=raw.suggestion.strip(),
        file=file.filename if file else None,
        line_start=line_start,
        line_end=line_end,
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def deduplicate_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Collapse findings sharing file, line, category, and normalized title.

    The most severe, then most confident, copy wins.
    """
    best: dict[tuple[object, ...], ReviewFinding] = {}
    for finding in findings:
        key = (finding.file, finding.line_start, finding.category, _normalize_text(finding.title))
        current = best.get(key)
        if current is None or _strength(finding) > _strength(current):
            best[key] = finding
    return list(best.values())


def _strength(finding: ReviewFinding) -> tuple[int, float]:
    return (SEVERITY_RANK[finding.severity], finding.confidence)


def _finding_order(finding: ReviewFinding) -> tuple[object, ...]:
    return (
        -SEVERITY_RANK[finding.severity],
        -finding.confidence,
        finding.file or "",
        finding.line_start or 0,
        finding.title,
    )


def _dedupe_test_suggestions(outputs: list[ModelReview]) -> list[TestSuggestion]:
    # ``file`` may name a test file that does not exist yet, so it is not checked against the diff.
    seen: set[tuple[str | None, str]] = set()
    suggestions = []
    for output in outputs:
        for raw in output.test_suggestions:
            key = (raw.file, _normalize_text(raw.description))
            if key not in seen:
                seen.add(key)
                suggestions.append(
                    TestSuggestion(description=raw.description.strip(), file=raw.file)
                )
    return suggestions


def _merge_summaries(outputs: list[ModelReview]) -> str:
    if not outputs:
        return NOTHING_TO_REVIEW_SUMMARY
    return "\n\n".join(_unique([o.summary.strip() for o in outputs]))


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))
