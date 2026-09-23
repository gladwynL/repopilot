# RepoPilot

AI-assisted GitHub pull request review.

> **Status: Phase 2 — AI review engine.**
> RepoPilot can fetch a GitHub pull request and produce an AI-assisted review: a summary, an
> overall risk level, structured findings with severity and confidence, and test suggestions.
> Findings are model output and can be wrong or incomplete; treat them as review assistance,
> not verdicts. Reviews are **not stored** yet, and RepoPilot **never posts to GitHub**.

## What RepoPilot will become

RepoPilot is planned as a pull request reviewer that will:

- ingest a GitHub repository or pull request and inspect its changed files and diffs
- summarize the pull request
- flag likely bugs and code-quality issues, and suggest missing tests
- produce structured review findings with severity and confidence metadata
- store review history and present it in a web UI

## Current state

**Phase 2 — AI review engine**

- `POST /api/reviews/github` runs the full pipeline: GitHub ingestion → review input → LLM →
  validated `ReviewResult`
- Provider abstraction with OpenAI (Responses API, strict structured outputs) as the first provider
- Deterministic file prioritization, per-request token budget, and chunking for large PRs
- Diffs are annotated with new-file line numbers; line references the diff cannot support are
  dropped rather than guessed
- Skipped, truncated, and diff-less files are reported as explicit limitations
- Conservative retries for transient provider failures; clear API errors for everything else

**Phase 1 — GitHub ingestion**

- Read-only GitHub REST client that fetches PR metadata and every changed file, following pagination
- Normalized, typed pull request schema (raw GitHub JSON stays inside the integration layer)
- `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}` endpoint
- Upstream failures (not found, auth, rate limit, outages) translated into clear API errors

**Phase 0 — foundation**

- FastAPI backend with `GET /health`, env-based settings, and CORS configuration
- SQLAlchemy 2 engine/session and Alembic migrations wired up (no models yet)
- PostgreSQL 16 via Docker Compose
- React + TypeScript + Vite frontend with a placeholder page
- Pytest, Vitest + Testing Library, Ruff, ESLint, and Prettier configured

**Not implemented yet:** persistence of reviews or review history, authentication, webhooks,
posting comments to GitHub, and any frontend beyond the placeholder.

See [docs/roadmap.md](docs/roadmap.md).

## Stack

| Area     | Tools                                          |
| -------- | ---------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2, Alembic    |
| AI       | OpenAI Responses API (structured outputs)      |
| Database | PostgreSQL 16                                  |
| Frontend | React, TypeScript, Vite                        |
| Testing  | Pytest, Vitest, Testing Library                |
| Quality  | Ruff, ESLint, Prettier                         |
| Infra    | Docker Compose (GitHub Actions CI planned)     |

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # routers; handlers stay thin
│   │   ├── core/         # settings
│   │   ├── db/           # SQLAlchemy base and session
│   │   ├── models/       # ORM models
│   │   ├── schemas/      # Pydantic API schemas
│   │   ├── services/     # business logic
│   │   │   ├── github.py # GitHub REST client
│   │   │   └── ai/       # review engine, input builder, prompts, LLM providers
│   │   └── main.py       # app factory
│   ├── alembic/          # migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/  components/  features/  hooks/  pages/  types/
│       └── main.tsx
├── docs/
├── docker-compose.yml
└── .env.example
```

## Local setup

Prerequisites: Python 3.12, Node.js 20+, Docker.

```bash
cp .env.example .env
```

### Database

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

The API runs at http://localhost:8000 — check http://localhost:8000/health.
Interactive API docs are at http://localhost:8000/docs.

### GitHub access

`GITHUB_TOKEN` is **optional**. Without it, public pull requests can be fetched using GitHub's
unauthenticated rate limit (60 requests/hour per IP; each PR ingestion uses at least two).
For private repositories or a higher limit, set a token in `.env`:

```bash
GITHUB_TOKEN=github_pat_...
```

A fine-grained personal access token with read-only **Pull requests** and **Contents** access
is enough. RepoPilot only reads from GitHub. Never commit `.env`.

### AI review

The review endpoint needs an OpenAI API key. Without one it returns `503`; everything else
keeps working.

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra   # any Responses API model with structured-output support
```

Budget and retry settings (`REVIEW_*`, `OPENAI_*`) are listed in [.env.example](.env.example).
Requests are sent with `store: false`, so OpenAI does not keep them as stored responses.

## API

### `POST /api/reviews/github`

Fetches a pull request and returns an AI-assisted review. Each call runs a fresh review
(nothing is cached or stored) and costs one or more model requests.

```bash
curl -X POST http://localhost:8000/api/reviews/github \
  -H "Content-Type: application/json" \
  -d '{"owner": "octocat", "repo": "Hello-World", "pull_number": 1}'
```

```json
{
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
```

(Illustrative output; actual findings depend on the model.)

- `category`: `bug`, `security`, `reliability`, `performance`, `maintainability`,
  `code_quality`, `testing`
- `severity` and `risk_level`: `low`, `medium`, `high`, `critical`. `risk_level` is `null`
  when no diff could be reviewed; no model call is made in that case.
- `confidence`: `0.0`–`1.0`; findings below `REVIEW_MIN_CONFIDENCE` are dropped
- `file` / `line_start` / `line_end`: set only when they point into the reviewed diff
  (line numbers refer to the new version of the file); otherwise `null`
- `skipped_files[].reason`: `no_patch`, `generated`, or `over_budget`

| Situation                                         | Status                      |
| ------------------------------------------------- | --------------------------- |
| Invalid request body                              | 422                         |
| GitHub errors                                     | same as the ingestion endpoint |
| AI not configured, or credentials/quota rejected  | 503                         |
| AI provider rate limited (`Retry-After` if known) | 503                         |
| AI provider unavailable or invalid model output   | 502                         |
| AI provider timed out                             | 504                         |

### How large PRs are handled

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
   No extra LLM call is used to merge.

Token counts are estimated as `ceil(characters / 3)`, which deliberately overestimates for
typical code and avoids depending on a model-specific tokenizer. Chunking trades cross-file
insight for bounded cost and latency: an issue spanning files in different chunks can be
missed, and the result says so in `limitations`.

### Limitations

- Review quality depends on the model: findings can be wrong, and real issues can be missed.
- Only diffs are reviewed. Full file contents and the rest of the repository are not fetched.
- Reviews are not persisted, and nothing is posted back to GitHub.
- The evaluation fixtures in `backend/tests/review_eval_cases.py` test the pipeline with
  canned model output; they do not measure model quality.

### `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}`

Fetches a pull request and its changed files from GitHub and returns them normalized:

```bash
curl http://localhost:8000/api/github/repos/octocat/Hello-World/pulls/1
```

```json
{
  "metadata": {
    "owner": "octocat",
    "repo": "Hello-World",
    "number": 1,
    "title": "...",
    "state": "closed",
    "draft": false,
    "merged": false,
    "author_login": "...",
    "base": { "ref": "master", "sha": "...", "repo_full_name": "octocat/Hello-World" },
    "head": { "ref": "patch-1", "sha": "...", "repo_full_name": "..." },
    "additions": 1,
    "deletions": 1,
    "changed_files": 1,
    "commits": 1
  },
  "files": [
    {
      "filename": "README",
      "status": "modified",
      "additions": 1,
      "deletions": 1,
      "changes": 2,
      "sha": "...",
      "patch": "@@ -1 +1 @@ ...",
      "previous_filename": null
    }
  ]
}
```

(Some fields are omitted above; see `/docs` for the full schema.) `patch` is `null` when GitHub
omits the diff, for example for binary files or very large changes.

| Situation                                  | Status |
| ------------------------------------------ | ------ |
| Invalid owner, repo, or PR number          | 422    |
| Repository or PR not found (or no access)  | 404    |
| GitHub rate limit hit (`Retry-After` set)  | 429    |
| GitHub rejected RepoPilot's token          | 502    |
| GitHub unavailable or unexpected response  | 502    |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at http://localhost:5173.

## Tests and checks

Tests do not need PostgreSQL, network access, or an OpenAI key. GitHub and OpenAI responses
are mocked, so the suite never makes paid API calls.

Backend (from `backend/`):

```bash
pytest
ruff check .
ruff format --check .
```

Frontend (from `frontend/`):

```bash
npm run test
npm run lint
npm run format:check
npm run build
```

## License

[MIT](LICENSE)
