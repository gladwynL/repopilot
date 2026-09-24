# Roadmap

| Phase | Scope                                                             | Status      |
| ----- | ----------------------------------------------------------------- | ----------- |
| 0     | Repository foundation: FastAPI, React, PostgreSQL, tests, linting | Done        |
| 1     | GitHub integration: fetch a PR and its diffs, normalize them      | Done        |
| 2     | AI review engine: summaries and structured findings from a PR     | Done        |
| 3     | Review persistence, caching, history, evaluation framework        | Done        |
| 4     | Review dashboard (frontend)                                       | Done        |
| 5+    | CI/CD, deployment                                                 | Not started |

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

## Phase 3 — persistence and evaluation

Delivered:

- Tables `reviews`, `review_findings`, `review_test_suggestions`, `evaluation_runs`,
  `evaluation_case_results` (Alembic revision `0001`)
- `ReviewRepository` / `EvaluationRepository` in `backend/app/repositories/` (all SQL lives there)
- `ReviewService` in `backend/app/services/reviews.py`: GitHub → cache lookup → review → save
- Cache key: SHA-256 of owner/repo (lowercased), PR number, `head_sha`, and `ReviewConfig`
  (provider, model, prompt version, budget settings, confidence floor)
- One current review per key (partial unique index), forced re-runs kept as history,
  saves for a key serialized with a PostgreSQL advisory lock
- `GET /api/reviews`, `GET /api/reviews/{id}`, `POST /api/reviews/github?force=true`, `GET /ready`
- Evaluation cases, per-condition checks, runner, and `python -m app.services.evaluation` CLI
- Disposable `test-db` Compose service and PostgreSQL integration tests (`tests/postgres/`)

Known limits:

- Live evaluation has not been run yet (no OpenAI key was available); no model-quality numbers
  exist.
- The evaluation suite has four tiny cases and checks behaviors, not accuracy.
- Concurrent uncached requests for the same PR can each pay for a model call (both results
  are stored; one becomes current).
- If the database fails after a successful model call, that review is lost (returns 503).
- History uses offset pagination; fine for dashboard-sized data, not for very deep paging.
- Reviews are never deleted; there is no retention policy yet.

## Phase 4 — review dashboard

Delivered (`frontend/src/`):

- Routes: `/` (dashboard and new review), `/reviews` (history), `/reviews/:reviewId`, 404
- Typed API client (`api/`) with central error mapping; pages never call `fetch` directly
- One `ReviewView` for fresh, cached, and historical reviews
- Small design system (Button, Badge, Card, Alert, EmptyState, PageHeader, fields, Spinner)
  with CSS Modules and system light/dark themes
- Vite dev/preview proxy for `/api`; `VITE_API_BASE_URL` for other setups
- Vitest + Testing Library tests with the API layer mocked

Known limits:

- No authentication: the dashboard and full history are visible to anyone who can reach it.
- A new review is a single long HTTP request with no progress reporting; leaving the page
  cancels the browser request (the backend may still finish and store the review).
- The cached/new badge is only known right after a review request; reviews opened later by
  URL show current/superseded status instead.
- File references are plain text, not links to GitHub.
- Screenshots in the README are still to be added.

## Phase 5 — next

Planned: CI/CD and deployment. Details will be planned when the phase begins.
