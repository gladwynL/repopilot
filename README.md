# RepoPilot

AI-assisted GitHub pull request review.

> **Status: Phase 1 — GitHub pull request ingestion.**
> RepoPilot can fetch a GitHub pull request and return its metadata and diffs in a normalized form.
> AI review (summaries, findings, test suggestions) is **not implemented yet**.

## What RepoPilot will become

RepoPilot is planned as a pull request reviewer that will:

- ingest a GitHub repository or pull request and inspect its changed files and diffs
- summarize the pull request
- flag likely bugs and code-quality issues, and suggest missing tests
- produce structured review findings with severity and confidence metadata
- store review history and present it in a web UI

## Current state

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

**Not implemented yet:** LLM calls, AI summaries or review findings, persistence of reviews,
authentication, webhooks, posting comments to GitHub, and any frontend beyond the placeholder.

See [docs/roadmap.md](docs/roadmap.md).

## Stack

| Area     | Tools                                          |
| -------- | ---------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2, Alembic    |
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
│   │   ├── services/     # business logic (github.py: GitHub REST client)
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

## API

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

Tests do not need PostgreSQL or network access; GitHub responses are mocked.

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
