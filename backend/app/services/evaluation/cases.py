"""The fixed evaluation suite: small PRs with expectations a sound review should meet.

The cases are intentionally tiny so a live run is cheap. They check specific behaviors
(catching an obvious bug, staying quiet on a clean change, acknowledging missing context);
they are not a benchmark of general review accuracy.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.pull_request import (
    FileStatus,
    GitRef,
    PullRequest,
    PullRequestFile,
    PullRequestMetadata,
)

REPO = "repopilot-evals/fixtures"


@dataclass(frozen=True)
class Expectations:
    min_high_confidence_bugs: int = 0
    """Bug findings with confidence >= ``HIGH_CONFIDENCE`` that must be present."""
    max_findings: int | None = None
    requires_test_suggestion: bool = False
    limitation_mentions: tuple[str, ...] = ()
    unreviewable_files: tuple[str, ...] = ()
    """Files without a diff: no finding may reference them."""


@dataclass(frozen=True)
class EvalCase:
    id: str
    description: str
    pr: PullRequest
    expectations: Expectations


def _file(
    filename: str,
    patch: str | None,
    *,
    additions: int,
    deletions: int,
    status: FileStatus = "modified",
) -> PullRequestFile:
    return PullRequestFile(
        filename=filename,
        status=status,
        additions=additions,
        deletions=deletions,
        changes=additions + deletions,
        sha=None,
        patch=patch,
        previous_filename=None,
    )


def _pr(number: int, title: str, body: str | None, *files: PullRequestFile) -> PullRequest:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return PullRequest(
        metadata=PullRequestMetadata(
            owner="repopilot-evals",
            repo="fixtures",
            number=number,
            title=title,
            body=body,
            state="open",
            draft=False,
            merged=False,
            author_login="eval-author",
            html_url=f"https://github.com/repopilot-evals/fixtures/pull/{number}",
            base=GitRef(ref="main", sha="0" * 40, repo_full_name=REPO),
            head=GitRef(
                ref=f"case-{number}",
                sha=f"{number:040x}",
                repo_full_name=REPO,
            ),
            created_at=timestamp,
            updated_at=timestamp,
            additions=sum(f.additions for f in files),
            deletions=sum(f.deletions for f in files),
            changed_files=len(files),
            commits=1,
        ),
        files=list(files),
    )


OBVIOUS_BUG = EvalCase(
    id="obvious_bug",
    description="A one-line change that always raises IndexError.",
    pr=_pr(
        1,
        "Simplify last_item",
        "Use explicit indexing.",
        _file(
            "src/collections_util.py",
            "@@ -1,3 +1,3 @@\n def last_item(items):\n-    return items[-1]\n"
            "+    return items[len(items)]\n",
            additions=1,
            deletions=1,
        ),
    ),
    expectations=Expectations(min_high_confidence_bugs=1),
)

MISSING_TEST = EvalCase(
    id="missing_test",
    description="New pricing behavior with a boundary and no accompanying test.",
    pr=_pr(
        2,
        "Add 10% discount for orders over 100",
        None,
        _file(
            "src/pricing.py",
            "@@ -1,2 +1,4 @@\n def discount(total):\n+    if total >= 100:\n"
            "+        return total * 0.9\n     return total\n",
            additions=2,
            deletions=0,
        ),
    ),
    expectations=Expectations(requires_test_suggestion=True),
)

CLEAN_CHANGE = EvalCase(
    id="clean_change",
    description="A documentation typo fix that warrants no findings.",
    pr=_pr(
        3,
        "Fix typo in usage docs",
        None,
        _file(
            "docs/usage.md",
            "@@ -1,2 +1,2 @@\n # Usage\n-Run the sever with make run.\n"
            "+Run the server with make run.\n",
            additions=1,
            deletions=1,
        ),
    ),
    expectations=Expectations(max_findings=0),
)

INCOMPLETE_CONTEXT = EvalCase(
    id="incomplete_context",
    description="The main change has no diff; only a config tweak is visible.",
    pr=_pr(
        4,
        "Rework payment processor",
        None,
        _file("src/payments/processor.py", None, additions=900, deletions=400),
        _file(
            "config/settings.yaml",
            "@@ -1 +1 @@\n-retries: 3\n+retries: 5\n",
            additions=1,
            deletions=1,
        ),
    ),
    expectations=Expectations(
        max_findings=0,
        limitation_mentions=("src/payments/processor.py",),
        unreviewable_files=("src/payments/processor.py",),
    ),
)

EVAL_CASES: tuple[EvalCase, ...] = (OBVIOUS_BUG, MISSING_TEST, CLEAN_CHANGE, INCOMPLETE_CONTEXT)
