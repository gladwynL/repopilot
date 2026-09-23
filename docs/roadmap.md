# Roadmap

| Phase | Scope                                                             | Status      |
| ----- | ----------------------------------------------------------------- | ----------- |
| 0     | Repository foundation: FastAPI, React, PostgreSQL, tests, linting | Done        |
| 1     | GitHub integration: fetch a PR and its diffs, normalize them      | Done        |
| 2     | AI review engine: summaries and structured findings from a PR     | Not started |
| 3+    | Review history persistence, review UI, CI/CD, deployment          | Not started |

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

## Phase 2 — AI review (next)

Planned: send the normalized `PullRequest` to an LLM, and produce a summary plus structured
findings with severity and confidence. Details will be planned when the phase begins.
