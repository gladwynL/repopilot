# Roadmap

| Phase | Scope                                                             | Status      |
| ----- | ----------------------------------------------------------------- | ----------- |
| 0     | Repository foundation: FastAPI, React, PostgreSQL, tests, linting | Done        |
| 1     | GitHub integration: fetch a PR and its diffs, normalize them      | Done        |
| 2     | AI review engine: summaries and structured findings from a PR     | Done        |
| 3     | Review persistence and history, model-quality evaluation          | Not started |
| 4+    | Review UI, CI/CD, deployment                                      | Not started |

## Phase 1 — GitHub ingestion

Delivered:

- `GitHubClient` in `backend/app/services/github.py` (async, read-only, paginated file fetching)
- Normalized `PullRequest` schema in `backend/app/schemas/pull_request.py`
- `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}`
- Mapping of GitHub failures to API errors

Known limits:

- GitHub's list-files endpoint returns at most 3,000 files per PR. Compare
  `metadata.changed_files` with `len(files)` to detect truncation.
- `patch` may be `null` (binary files, very large diffs).
- Full file contents are not fetched; only diffs.

## Phase 2 — AI review engine

Pipeline: `PullRequest` → `ReviewInputBuilder` (skip, rank, truncate, chunk) → prompt layer →
`ReviewModel` provider (OpenAI) → validated `ModelReview` per chunk → `ReviewEngine` merge
(file/line grounding, confidence floor, deduplication) → `ReviewResult`.

Code lives in `backend/app/services/ai/`:

| Module               | Responsibility                                         |
| -------------------- | ------------------------------------------------------ |
| `base.py`            | Provider protocol, model-output schema, AI error types |
| `diff.py`            | Unified-diff parsing for new-file line numbers         |
| `review_input.py`    | Prepared-input data types                              |
| `input_builder.py`   | File selection, budgeting, truncation, chunking        |
| `prompts.py`         | Stable review instructions and PR/diff rendering       |
| `openai_provider.py` | OpenAI Responses API calls, retries, error translation |
| `review_engine.py`   | Orchestration, merging, deduplication                  |

Known limits:

- Chunks are reviewed independently; cross-chunk issues may be missed.
- Multi-chunk summaries are concatenated rather than synthesized.
- Line references cover the new side of the diff only; findings about removed code carry no
  line number.
- A failure in any chunk fails the whole review (no partial results).
- Token counts are estimated (`ceil(chars / 3)`), not measured with the model's tokenizer.

## Phase 3 — next

Planned: persist `ReviewResult` (keyed by PR and `head_sha`, with `model` and
`prompt_version`), review history, and live-model evaluation against the cases in
`backend/tests/review_eval_cases.py`. Details will be planned when the phase begins.
