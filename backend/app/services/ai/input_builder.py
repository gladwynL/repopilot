"""Turns a normalized ``PullRequest`` into budgeted, chunked review input.

Selection strategy (deterministic, no randomness):

1. Files without a patch and generated/vendored files are skipped and recorded.
2. Remaining files are ranked by tier, then by lines changed (descending), then by path:
   source code, then security-sensitive config (CI, containers, dependency manifests),
   then tests, then everything else (docs, data), then deleted files.
3. Each file's diff is cut to the per-file budget at a line boundary.
4. Files are packed first-fit, in rank order, into at most ``max_chunks`` chunks, each of
   which must fit the per-request budget together with the shared PR context. Files that
   fit nowhere are skipped as over budget.

Sizes are estimated as ``ceil(chars / 3)`` tokens. That overestimates typical English and
code tokenization (roughly 3.5-4 chars per token), so budgets err on the safe side without
depending on a model-specific tokenizer.
"""

import math
from pathlib import PurePosixPath

from app.schemas.pull_request import PullRequest, PullRequestFile
from app.schemas.review import SkippedFile, SkipReason
from app.services.ai import prompts
from app.services.ai.diff import DiffLine, parse_patch
from app.services.ai.review_input import ManifestEntry, PreparedFile, ReviewChunk, ReviewInput

CHARS_PER_TOKEN = 3
MAX_NAMES_IN_LIMITATION = 10

# fmt: off
_SOURCE_SUFFIXES = frozenset({
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt",
    ".kts", ".rb", ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".swift", ".scala", ".sql",
    ".sh", ".bash", ".ps1", ".vue", ".svelte", ".dart", ".ex", ".exs", ".lua", ".tf",
})
_SENSITIVE_NAMES = frozenset({
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "requirements.txt", "pyproject.toml", "package.json", "setup.py", "setup.cfg", "go.mod",
    "cargo.toml", "pom.xml", "build.gradle", "gemfile", ".env.example",
})
_GENERATED_NAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "pipfile.lock",
    "cargo.lock", "go.sum", "gemfile.lock", "composer.lock",
})
# fmt: on
_GENERATED_SUFFIXES = (".min.js", ".min.css", ".map", ".snap", "_pb2.py", ".pb.go")
_GENERATED_DIRS = frozenset({"node_modules", "vendor", "dist", "__snapshots__"})
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs"})


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def is_generated(path: str) -> bool:
    p = PurePosixPath(path.lower())
    return (
        p.name in _GENERATED_NAMES
        or p.name.endswith(_GENERATED_SUFFIXES)
        or ".generated." in p.name
        or any(part in _GENERATED_DIRS for part in p.parts[:-1])
    )


def is_test(path: str) -> bool:
    p = PurePosixPath(path.lower())
    stem = p.name.split(".")[0]
    return (
        any(part in _TEST_DIRS for part in p.parts[:-1])
        or stem.startswith("test_")
        or stem.endswith(("_test", "_spec"))
        or ".test." in p.name
        or ".spec." in p.name
    )


def _tier(file: PullRequestFile) -> int:
    p = PurePosixPath(file.filename.lower())
    if file.status == "removed":
        return 4
    if is_test(file.filename):
        return 2
    if p.suffix in _SOURCE_SUFFIXES:
        return 0
    if (
        p.name in _SENSITIVE_NAMES
        or p.name.startswith("dockerfile")
        or (p.parts[:2] == (".github", "workflows"))
    ):
        return 1
    return 3


def priority_key(file: PullRequestFile) -> tuple[int, int, str]:
    return (_tier(file), -file.changes, file.filename)


class ReviewInputBuilder:
    def __init__(self, *, chunk_token_budget: int, max_chunks: int, max_file_tokens: int) -> None:
        self._chunk_budget = chunk_token_budget
        self._max_chunks = max_chunks
        self._max_file_tokens = max_file_tokens

    def build(self, pr: PullRequest) -> ReviewInput:
        skipped: dict[str, SkipReason] = {}
        candidates: list[PullRequestFile] = []
        for file in pr.files:
            if not file.patch:
                skipped[file.filename] = "no_patch"
            elif is_generated(file.filename):
                skipped[file.filename] = "generated"
            else:
                candidates.append(file)

        # Size the shared context with the longest note any candidate could receive, so the
        # final (actual) context can only be smaller than what was budgeted.
        worst_note = max(prompts.REVIEWABLE_FILE_NOTES, key=len)
        worst_context = self._render_context(
            pr, {f.filename: worst_note for f in candidates}, skipped
        )
        worst_chunk_note = prompts.render_chunk_note(self._max_chunks - 1, self._max_chunks)
        capacity = self._chunk_budget - estimate_tokens(worst_context + worst_chunk_note)

        file_budget = min(self._max_file_tokens, capacity)
        prepared = [
            self._prepare(file, file_budget) for file in sorted(candidates, key=priority_key)
        ]
        chunks = self._pack(prepared, capacity, skipped)

        notes = {
            file.filename: prompts.manifest_note(truncated=file.truncated)
            for chunk in chunks
            for file in chunk.files
        }
        return ReviewInput(
            metadata=pr.metadata,
            context=self._render_context(pr, notes, skipped),
            chunks=tuple(chunks),
            skipped_files=tuple(
                SkippedFile(filename=f.filename, reason=skipped[f.filename])
                for f in pr.files
                if f.filename in skipped
            ),
            limitations=tuple(self._limitations(pr, chunks, skipped)),
            files_considered=len(pr.files),
        )

    def _render_context(
        self, pr: PullRequest, notes: dict[str, str], skipped: dict[str, SkipReason]
    ) -> str:
        manifest = [
            ManifestEntry(
                filename=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                note=notes.get(f.filename)
                or prompts.manifest_note(skip_reason=skipped[f.filename]),
            )
            for f in pr.files
            if f.filename in notes or f.filename in skipped
        ]
        return prompts.render_pr_context(pr.metadata, manifest, pr.metadata.changed_files)

    def _prepare(self, file: PullRequestFile, token_budget: int) -> PreparedFile:
        lines = parse_patch(file.patch or "")
        prepared = self._prepared(file, lines, omitted=0)
        if estimate_tokens(prompts.render_file(prepared)) <= token_budget:
            return prepared

        # Keep the longest prefix of lines that fits, leaving room for the truncation notice.
        fixed = prompts.render_file(self._prepared(file, [], omitted=len(lines)))
        remaining_chars = token_budget * CHARS_PER_TOKEN - len(fixed)
        kept: list[DiffLine] = []
        for line in lines:
            remaining_chars -= len(prompts.render_diff_line(line)) + 1
            if remaining_chars < 0:
                break
            kept.append(line)
        return self._prepared(file, kept, omitted=len(lines) - len(kept))

    @staticmethod
    def _prepared(file: PullRequestFile, lines: list[DiffLine], omitted: int) -> PreparedFile:
        return PreparedFile(
            filename=file.filename,
            status=file.status,
            additions=file.additions,
            deletions=file.deletions,
            previous_filename=file.previous_filename,
            lines=tuple(lines),
            omitted_lines=omitted,
        )

    def _pack(
        self, files: list[PreparedFile], capacity: int, skipped: dict[str, SkipReason]
    ) -> list[ReviewChunk]:
        bins: list[list[PreparedFile]] = []
        used: list[int] = []
        for file in files:
            cost = estimate_tokens(prompts.render_file(file))
            if not file.lines or cost > capacity:
                skipped[file.filename] = "over_budget"
                continue
            target = next((i for i, u in enumerate(used) if u + cost <= capacity), None)
            if target is None and len(bins) < self._max_chunks:
                bins.append([])
                used.append(0)
                target = len(bins) - 1
            if target is None:
                skipped[file.filename] = "over_budget"
                continue
            bins[target].append(file)
            used[target] += cost
        return [
            ReviewChunk(files=tuple(b), estimated_tokens=u) for b, u in zip(bins, used, strict=True)
        ]

    @staticmethod
    def _limitations(
        pr: PullRequest, chunks: list[ReviewChunk], skipped: dict[str, SkipReason]
    ) -> list[str]:
        def names(filenames: list[str]) -> str:
            shown = ", ".join(filenames[:MAX_NAMES_IN_LIMITATION])
            extra = len(filenames) - MAX_NAMES_IN_LIMITATION
            return shown + (f" and {extra} more" if extra > 0 else "")

        def by_reason(reason: SkipReason) -> list[str]:
            return [f.filename for f in pr.files if skipped.get(f.filename) == reason]

        limitations = []
        if missing := by_reason("no_patch"):
            limitations.append(
                f"GitHub provided no diff for {len(missing)} file(s) (binary or too large), "
                f"so they were not reviewed: {names(missing)}."
            )
        if generated := by_reason("generated"):
            limitations.append(
                f"Skipped {len(generated)} generated or vendored file(s): {names(generated)}."
            )
        if over := by_reason("over_budget"):
            limitations.append(
                f"{len(over)} file(s) were not reviewed because the PR exceeds the review "
                f"budget: {names(over)}."
            )
        truncated = [f.filename for c in chunks for f in c.files if f.truncated]
        if truncated:
            limitations.append(
                f"Only the beginning of the diff was reviewed for {len(truncated)} file(s): "
                f"{names(truncated)}."
            )
        if len(pr.files) < pr.metadata.changed_files:
            limitations.append(
                f"GitHub returned {len(pr.files)} of {pr.metadata.changed_files} changed files; "
                "the rest were not reviewed."
            )
        if len(chunks) > 1:
            limitations.append(
                f"The PR was reviewed in {len(chunks)} separate parts; issues that span files "
                "in different parts may be missed."
            )
        return limitations
