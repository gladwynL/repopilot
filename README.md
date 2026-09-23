# RepoPilot

AI-assisted GitHub pull request review.

> **Status: Phase 0 — project foundation only.**
> GitHub integration, pull request ingestion, and AI review are **not implemented yet**.
> The app currently serves a health endpoint and a placeholder web page.

## What RepoPilot will become

RepoPilot is planned as a pull request reviewer that will:

- ingest a GitHub repository or pull request and inspect its changed files and diffs
- summarize the pull request
- flag likely bugs and code-quality issues, and suggest missing tests
- produce structured review findings with severity and confidence metadata
- store review history and present it in a web UI

## Current state (Phase 0)

- FastAPI backend with `GET /health`, env-based settings, and CORS configuration
- SQLAlchemy 2 engine/session and Alembic migrations wired up (no models yet)
- PostgreSQL 16 via Docker Compose
- React + TypeScript + Vite frontend with a placeholder page
- Pytest, Vitest + Testing Library, Ruff, ESLint, and Prettier configured

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
│   │   ├── services/     # business logic
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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at http://localhost:5173.

## Tests and checks

The Phase 0 tests do not need PostgreSQL running.

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
