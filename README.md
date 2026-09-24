# RepoPilot

AI-assisted GitHub pull request review.

> **Status: Phase 4 — review dashboard.**
> RepoPilot fetches a GitHub pull request, produces an AI-assisted review (summary, risk level,
> findings with severity and confidence, test suggestions), stores it in PostgreSQL, and
> presents it in a web dashboard with review history. Unchanged PRs are served from storage
> without another model call.
> Findings are model output and can be wrong or incomplete; treat them as review assistance,
> not verdicts. RepoPilot **never posts to GitHub**. There is **no authentication**: anyone who
> can reach the app can run reviews and read the full history. It is not deployed anywhere.

## What RepoPilot will become

RepoPilot is planned as a pull request reviewer that will:

- ingest a GitHub repository or pull request and inspect its changed files and diffs
- summarize the pull request
- flag likely bugs and code-quality issues, and suggest missing tests
- produce structured review findings with severity and confidence metadata
- store review history and present it in a web UI

## Current state

**Phase 4 — review dashboard**

- React dashboard to start a review from a PR URL or owner/repo/number, with an honest
  pending state (elapsed time, no fake progress)
- Review page: AI-assessed risk, summary, findings (severity, category, confidence,
  file/line), test suggestions, coverage and limitations, cached/new and current/superseded
  markers, and a deliberate "Run review again"
- Paginated, filterable review history; every stored review has a shareable URL
- Friendly error, loading, and empty states; responsive down to phone width; light and dark
  themes follow the system setting

**Phase 3 — persistence and evaluation**

- Completed reviews are stored in PostgreSQL (reviews, findings, test suggestions)
- Reviews are cached per PR commit and review configuration; repeat requests skip the model
- `?force=true` re-runs a review and keeps earlier runs in history
- `GET /api/reviews` (paginated history) and `GET /api/reviews/{id}`
- `GET /ready` readiness check (database connectivity); `/health` stays a pure liveness check
- Evaluation runner and CLI that score the fixture suite against the configured model and
  store each run

**Phase 2 — AI review engine**

- `POST /api/reviews/github` runs GitHub ingestion → review input → LLM → validated `ReviewResult`
- Provider abstraction with OpenAI (Responses API, strict structured outputs) as the first provider
- Deterministic file prioritization, per-request token budget, and chunking for large PRs
- Diffs are annotated with new-file line numbers; line references the diff cannot support are
  dropped rather than guessed
- Skipped, truncated, and diff-less files are reported as explicit limitations

**Phase 1 — GitHub ingestion**

- Read-only GitHub REST client that fetches PR metadata and every changed file, with pagination
- `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}`

**Phase 0 — foundation**

- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 via Docker Compose, React + Vite placeholder
- Pytest, Vitest + Testing Library, Ruff, ESLint, and Prettier

**Not implemented yet:** authentication, webhooks, posting comments to GitHub, CI/CD, and
deployment.

See [docs/roadmap.md](docs/roadmap.md).

## Stack

| Area     | Tools                                       |
| -------- | ------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| AI       | OpenAI Responses API (structured outputs)   |
| Database | PostgreSQL 16                               |
| Frontend | React 19, TypeScript, Vite, React Router    |
| Testing  | Pytest, Vitest, Testing Library             |
| Quality  | Ruff, ESLint, Prettier                      |
| Infra    | Docker Compose (GitHub Actions CI planned)  |

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # routers and dependencies; handlers stay thin
│   │   ├── core/           # settings, logging
│   │   ├── db/             # SQLAlchemy base, engine/session factories, errors
│   │   ├── models/         # ORM models (reviews, evaluation runs)
│   │   ├── repositories/   # all SQL lives here
│   │   ├── schemas/        # Pydantic API schemas
│   │   ├── services/
│   │   │   ├── github.py   # GitHub REST client
│   │   │   ├── reviews.py  # cache-aware review orchestration
│   │   │   ├── ai/         # review engine, input builder, prompts, LLM providers
│   │   │   └── evaluation/ # evaluation cases, checks, runner, CLI
│   │   └── main.py         # app factory
│   ├── alembic/            # migrations
│   └── tests/              # unit tests; tests/postgres/ needs a real database
├── frontend/
│   └── src/
│       ├── api/            # typed API client, error mapping
│       ├── components/     # design-system primitives and app shell
│       ├── features/reviews/ # review form, review view, history table, labels
│       ├── hooks/          # data loading, elapsed-time
│       ├── pages/          # route screens
│       ├── types/          # API response types (mirror backend schemas)
│       └── utils/          # formatting
├── docs/
├── docker-compose.yml
└── .env.example
```

## Local setup

Prerequisites: Python 3.12, Node.js 20+, Docker.

```bash
cp .env.example .env
```

The app runs as three processes, each in its own terminal:

1. PostgreSQL: `docker compose up -d db`
2. Backend (from `backend/`): `uvicorn app.main:app --reload` → http://localhost:8000
3. Frontend (from `frontend/`): `npm run dev` → http://localhost:5173

First-time setup for each is below.

### Database

PostgreSQL is required for the review endpoints (reviews are stored) and for evaluation runs.

```bash
docker compose up -d db
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000. `/health` reports liveness, `/ready` also checks the
database, and interactive API docs are at http://localhost:8000/docs.

Migrations live in `backend/alembic/versions/`. Apply them with `alembic upgrade head`; roll
the Phase 3 schema back with `alembic downgrade base`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In development (and `npm run preview`), the Vite server proxies
`/api` to the backend at `http://localhost:8000`, so no CORS setup is needed.

Frontend configuration (`frontend/.env.example`; copy to `frontend/.env` to change it):

| Variable            | Default                 | Purpose                                                        |
| ------------------- | ----------------------- | -------------------------------------------------------------- |
| `VITE_API_BASE_URL` | empty (same origin)     | API origin baked into the build, e.g. `http://localhost:8000`. |
| `API_PROXY_TARGET`  | `http://localhost:8000` | Where the dev/preview proxy sends `/api` requests.             |

`VITE_*` values are compiled into the browser bundle, so never put secrets there. If you set
`VITE_API_BASE_URL` to another origin, add the frontend's origin to the backend's
`CORS_ORIGINS`.

### GitHub access

`GITHUB_TOKEN` is **optional**. Without it, public pull requests can be fetched using GitHub's
unauthenticated rate limit (60 requests/hour per IP; each PR fetch uses at least two).
For private repositories or a higher limit, set a fine-grained token with read-only
**Pull requests** and **Contents** access in `.env`. RepoPilot only reads from GitHub.
Never commit `.env`.

### AI review

A fresh review needs an OpenAI API key. Without one, cache misses return `503`; cached reviews,
history, and everything else keep working.

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra   # any Responses API model with structured-output support
```

Budget and retry settings (`REVIEW_*`, `OPENAI_*`) are listed in [.env.example](.env.example).
Requests are sent with `store: false`, so OpenAI does not keep them as stored responses.

## Web app

Screenshots: _to be added._

| Route                | Screen                                                              |
| -------------------- | ------------------------------------------------------------------- |
| `/`                  | Dashboard: start a review, see the five most recent reviews         |
| `/reviews`           | History: newest first, filter by owner/repo/PR number, 20 per page  |
| `/reviews/:reviewId` | One stored review (the same view is used for new and old reviews)   |
| anything else        | 404 page                                                            |

**Review flow**

1. Paste a PR URL (`https://github.com/owner/repo/pull/123`) or enter owner, repository, and
   PR number. Input is validated with the same rules as the API.
2. While the request runs, the page shows the target PR, the elapsed time, and a static
   description of what RepoPilot does. The API reports no progress, so the page shows none.
3. When the review is ready, its page opens. A **Cached review** badge means this exact
   commit was already reviewed with the same settings and no new AI request was made;
   **New review** means one was.
4. **Run review again** always runs a new AI review of the PR's current commit (it calls
   `POST /api/reviews/github?force=true`) and opens the result. The earlier review stays in
   history marked **Superseded**.

**Reading a review**

- *AI-assessed risk*: low, medium, high, or critical, shown with a distinct shape and a
  label as well as a color. **Not assessed** means no diff could be reviewed.
- *Findings* are shown in the API's order (most severe, most confident first) and can be
  filtered by severity and category. Confidence is the model's own estimate, rounded to a
  whole percentage; it is not a calibrated probability.
- File references (`path:line` or `path:start–end`) are plain text. They only appear when the
  line is in the reviewed diff, and they are not linked to GitHub, because a link to a
  specific line can't be built reliably for every case (for example deleted files or forks).
- *Coverage & limitations* lists skipped files (with the reason), partially reviewed files,
  and limitations reported by the pipeline and the model.

## API

### `POST /api/reviews/github[?force=true]`

Reviews a pull request, or returns the stored review if this exact PR commit was already
reviewed under the same configuration.

```bash
curl -X POST http://localhost:8000/api/reviews/github \
  -H "Content-Type: application/json" \
  -d '{"owner": "octocat", "repo": "Hello-World", "pull_number": 1}'
```

```json
{
  "id": "5b0c3c3e-8a3e-4b7e-9d0e-2f1f6c1a9e10",
  "created_at": "2026-09-23T18:40:12.345678Z",
  "is_current": true,
  "cached": false,
  "review": {
    "pull_request": { "owner": "octocat", "repo": "Hello-World", "number": 1, "head_sha": "7044a8a..." },
    "model": "gpt-5.6-terra",
    "prompt_version": "2026-09-23.1",
    "summary": "Replaces the README greeting with setup instructions...",
    "risk_level": "low",
    "findings": [
      {
        "category": "maintainability",
        "severity": "low",
        "confidence": 0.7,
        "title": "Commands and descriptions are run together",
        "description": "Each line joins a shell command and its explanation with no separator...",
        "suggestion": "Put commands in a fenced code block and descriptions on separate lines.",
        "file": "README",
        "line_start": 2,
        "line_end": 4
      }
    ],
    "test_suggestions": [],
    "reviewed_files": ["README"],
    "truncated_files": [],
    "skipped_files": [],
    "limitations": []
  }
}
```

(Illustrative output; actual findings depend on the model.)

- `cached`: `true` when a stored review was returned and no model call was made
- `category`: `bug`, `security`, `reliability`, `performance`, `maintainability`,
  `code_quality`, `testing`
- `severity` and `risk_level`: `low`, `medium`, `high`, `critical`. `risk_level` is `null`
  when no diff could be reviewed; no model call is made in that case.
- `confidence`: `0.0`–`1.0`; findings below `REVIEW_MIN_CONFIDENCE` are dropped
- `file` / `line_start` / `line_end`: set only when they point into the reviewed diff
  (line numbers refer to the new version of the file); otherwise `null`
- `skipped_files[].reason`: `no_patch`, `generated`, or `over_budget`

#### Caching and re-runs

Every request fetches the PR from GitHub first (to learn its current `head_sha`), then looks
up a stored review by **cache key**: a SHA-256 over

- repository owner and name (case-insensitive) and PR number
- the PR's `head_sha`
- the review configuration: provider, model, prompt version, `REVIEW_CHUNK_TOKEN_BUDGET`,
  `REVIEW_MAX_CHUNKS`, `REVIEW_MAX_FILE_TOKENS`, and `REVIEW_MIN_CONFIDENCE`

Timeouts, retry counts, and the output-token cap are excluded: they affect whether a review
succeeds, not what it says.

- **Hit:** the stored review is returned with `cached: true`. OpenAI is not called.
- **Miss** (new commit, or a changed model/prompt/budget): a new review runs and is stored.
- **`force=true`:** a new review always runs. It becomes the *current* review for its key; the
  previous one stays in history with `is_current: false`.

Each key has at most one current review. This is enforced by a partial unique index
(`cache_key WHERE is_current`), and saves for the same key are serialized with a PostgreSQL
advisory lock. If two uncached requests for the same PR race, both reviews are stored: the first
to finish becomes current, and the other is kept as history. Both requests pay for a model call;
RepoPilot does not use distributed locks to prevent that.

| Situation                                         | Status                          |
| ------------------------------------------------- | ------------------------------- |
| Invalid request body or `force` value             | 422                             |
| GitHub errors                                     | same as the ingestion endpoint  |
| AI not configured (cache miss), credentials/quota | 503                             |
| AI provider rate limited (`Retry-After` if known) | 503                             |
| AI provider unavailable or invalid model output   | 502                             |
| AI provider timed out                             | 504                             |
| Database unavailable                              | 503                             |

If the database fails after the model call succeeds, the request returns `503` and the review
is not stored. The model call is not retried automatically.

### `GET /api/reviews`

Paginated review history, newest first. Optional filters: `owner`, `repo`, `pull_number`
(owner/repo are case-insensitive). `limit` is 1–100 (default 20); `offset` ≥ 0.

```json
{
  "items": [
    {
      "id": "5b0c3c3e-...",
      "owner": "octocat",
      "repo": "Hello-World",
      "pull_number": 1,
      "head_sha": "7044a8a...",
      "provider": "openai",
      "model": "gpt-5.6-terra",
      "prompt_version": "2026-09-23.1",
      "risk_level": "low",
      "finding_count": 1,
      "is_current": true,
      "created_at": "2026-09-23T18:40:12.345678Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### `GET /api/reviews/{id}`

Returns one stored review (same shape as the POST response, without `cached`) from the
database only; GitHub and OpenAI are not contacted. Unknown IDs return `404`.

### `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}`

Fetches a pull request and its changed files from GitHub and returns them normalized
(metadata plus a `files` list with `patch`, which is `null` for binary or very large diffs).
Nothing is stored.

| Situation                                  | Status |
| ------------------------------------------ | ------ |
| Invalid owner, repo, or PR number          | 422    |
| Repository or PR not found (or no access)  | 404    |
| GitHub rate limit hit (`Retry-After` set)  | 429    |
| GitHub rejected RepoPilot's token          | 502    |
| GitHub unavailable or unexpected response  | 502    |

## What is stored

Tables: `reviews`, `review_findings`, `review_test_suggestions`, `evaluation_runs`,
`evaluation_case_results`. Reviews store the structured result plus the cache key, the review
configuration, and the provider. Small lists (reviewed, truncated, and skipped files;
limitations) are JSONB columns.

Not stored: prompts, diffs or source code, raw provider responses, API keys, GitHub tokens,
or request headers.

## How large PRs are handled

RepoPilot enforces its own input budget instead of relying on the model's context window:

1. Files with no diff from GitHub (binary or very large) and generated/vendored files
   (lockfiles, minified bundles, `vendor/`, `dist/`, ...) are skipped and listed.
2. The remaining files are ranked: source code, then security-sensitive config (CI, Docker,
   dependency manifests), then tests, then other files, then deletions. Within a tier,
   larger changes come first; ties break on path. There is no randomness.
3. Any single diff larger than `REVIEW_MAX_FILE_TOKENS` is cut at a line boundary.
4. Files are packed into at most `REVIEW_MAX_CHUNKS` requests of `REVIEW_CHUNK_TOKEN_BUDGET`
   estimated tokens each; anything left over is skipped as over budget.
5. Chunks are reviewed independently and merged in code: the highest risk wins, findings are
   deduplicated on file, line, category, and normalized title, and limitations are combined.

Token counts are estimated as `ceil(characters / 3)`, which deliberately overestimates for
typical code. An issue spanning files in different chunks can be missed, and the result says
so in `limitations`.

## Evaluation

`backend/app/services/evaluation/` contains a small fixed suite of evaluation cases (an obvious
bug, a behavior change without tests, a clean docs change, and a PR whose main diff is missing)
with expectations such as "at least one bug finding with confidence ≥ 0.8" or "no findings".
The runner reviews each case with the configured model, checks the expectations, and reports:

- per case: pass/fail, which conditions failed, latency, the structured review, or a
  sanitized provider error
- per run: passed, failed, and errored counts, the case pass rate, and a pass rate for each
  condition kind (e.g. `detects_expected_bug`, `finding_limit`, `suggests_test`)

These are behavior checks on four tiny cases, not an accuracy benchmark.

Run it against the live model (makes a few paid model calls; needs `OPENAI_API_KEY` and a
migrated database, since runs are stored in `evaluation_runs`):

```bash
cd backend
python -m app.services.evaluation            # add --no-persist to skip the database
python -m app.services.evaluation --json run.json
```

Exit code `0` means every case passed, `1` means some failed or errored, and `2` means a
configuration or storage problem.

**Live evaluation status:** not run yet. No OpenAI API key was available when Phase 3 was
built, so no live model-quality results exist. The automated tests exercise the runner with
canned model output only.

## Tests and checks

Backend (from `backend/`):

```bash
pytest
ruff check .
ruff format --check .
```

The default `pytest` run needs no database, network access, or OpenAI key. GitHub and OpenAI
are mocked, and review storage uses an in-memory fake. Tests in `tests/postgres/` (migrations,
repositories, concurrency, end-to-end API) need a real PostgreSQL and are skipped unless
`TEST_DATABASE_URL` is set. Use the disposable `test-db` service, which keeps its data in
memory and never touches the development database:

```bash
docker compose --profile test up -d --wait test-db
TEST_DATABASE_URL=postgresql+psycopg://repopilot:repopilot@localhost:55432/repopilot_test pytest
docker compose --profile test rm -sf test-db
```

The Postgres tests refuse to run against a database whose name does not end in `_test`.

Frontend (from `frontend/`):

```bash
npm run test
npm run lint
npm run format:check
npm run build
```

Frontend tests (Vitest + Testing Library) mock the API layer, so they need no backend.

## License

[MIT](LICENSE)
