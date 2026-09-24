# API reference

All endpoints are served by FastAPI under the app's own origin. When `AUTH_ENABLED=true`, every
`/api/reviews*` and `/api/github/*` endpoint requires a signed-in, allowlisted session (`401`
otherwise). In development, interactive docs are at `/docs`; they are disabled in production.

Errors always use the shape `{"detail": "<message>"}` with fixed, user-safe messages.

## Reviews

### `POST /api/reviews/github[?force=true]`

Reviews a pull request, or returns the stored review if this exact commit was already reviewed
under the same configuration.

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

The response above is illustrative; real findings depend on the model.

| Field | Meaning |
| --- | --- |
| `cached` | `true` when a stored review was returned and no model call was made |
| `is_current` | Whether cache lookups return this review; `false` once a forced re-run replaces it |
| `category` | `bug`, `security`, `reliability`, `performance`, `maintainability`, `code_quality`, `testing` |
| `severity`, `risk_level` | `low`, `medium`, `high`, `critical`. `risk_level` is `null` when no diff could be reviewed; no model call is made in that case. |
| `confidence` | `0.0`–`1.0`, as reported by the model. Findings below `REVIEW_MIN_CONFIDENCE` are dropped. |
| `file`, `line_start`, `line_end` | Set only when they point into the reviewed diff (new-file line numbers); otherwise `null` |
| `skipped_files[].reason` | `no_patch`, `generated`, or `over_budget` |

**Caching.** Every request fetches the PR from GitHub first, to learn its current `head_sha`,
then looks for a stored review under a cache key: a SHA-256 over

- the owner and repository (lowercased) and the PR number
- `head_sha`
- the review configuration: provider, model, prompt version, `REVIEW_CHUNK_TOKEN_BUDGET`,
  `REVIEW_MAX_CHUNKS`, `REVIEW_MAX_FILE_TOKENS`, `REVIEW_MIN_CONFIDENCE`

Timeouts, retry counts, and the output-token cap are left out: they affect whether a review
succeeds, not what it says.

- **Hit:** the stored review is returned with `cached: true`. OpenAI is not called.
- **Miss** (new commit, or a different model, prompt, or budget): a new review runs and is stored.
- **`force=true`:** a new review always runs and becomes the current one. The previous review
  stays in history with `is_current: false`.

Each key has at most one current review. A partial unique index enforces this, and saves for
the same key are serialized with a PostgreSQL advisory lock. If two uncached requests for the
same PR race, both results are stored: the first to finish becomes current and the other is
kept as history. Both requests pay for a model call.

| Situation | Status |
| --- | --- |
| Invalid body or `force` value | 422 |
| Not signed in (auth enabled) | 401 |
| GitHub errors | as for the ingestion endpoint below |
| AI not configured (on a cache miss), or credentials/quota rejected | 503 |
| AI provider rate limited (`Retry-After` if known) | 503 |
| All review slots busy (`REVIEW_MAX_CONCURRENT`) | 429, `Retry-After: 30` |
| AI provider unavailable or invalid model output | 502 |
| AI provider timed out | 504 |
| Database unavailable | 503 |

If the database fails after a successful model call, the request returns `503` and the review
is not stored. The model call is not retried automatically.

### `GET /api/reviews`

Paginated review history, newest first. Optional filters: `owner`, `repo` (both
case-insensitive), and `pull_number`. `limit` is 1–100 (default 20); `offset` is ≥ 0.

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

Returns one stored review, in the same shape as the POST response but without `cached`. It
reads the database only; GitHub and OpenAI are not contacted. Unknown IDs return `404`.

## GitHub ingestion

### `GET /api/github/repos/{owner}/{repo}/pulls/{pull_number}`

Fetches a pull request and every changed file (following pagination) and returns them
normalized. `patch` is `null` when GitHub provides no diff (binary or very large files).
Nothing is stored.

| Situation | Status |
| --- | --- |
| Invalid owner, repo, or PR number | 422 |
| Repository or PR not found (or no access) | 404 |
| GitHub rate limit (`Retry-After` set) | 429 |
| GitHub rejected RepoPilot's token | 502 |
| GitHub unavailable or unexpected response | 502 |

## Authentication

| Endpoint | Purpose |
| --- | --- |
| `GET /api/auth/me` | `{"auth_enabled": bool, "user": {login, name, avatar_url} \| null}` |
| `GET /api/auth/login?next=/path` | Redirects to GitHub with `state` and a PKCE challenge |
| `GET /api/auth/callback` | Verifies `state`, exchanges the code, checks the allowlist, sets the session |
| `POST /api/auth/logout` | Clears the session (`204`) |

On a failed sign-in the callback redirects to `/?auth_error=<code>`, where the code is one of
`invalid_state`, `access_denied`, `github_error`, or `not_allowed`.

## Probes

| Endpoint | Meaning |
| --- | --- |
| `GET /health` | Liveness: the process is up. Touches nothing external. |
| `GET /ready` | Readiness: the database answers `SELECT 1`. `503` otherwise. |

## What is stored

Tables: `reviews`, `review_findings`, `review_test_suggestions`, `evaluation_runs`, and
`evaluation_case_results`. Each review stores the structured result, the cache key, the review
configuration, and the provider. Short lists (reviewed, truncated, and skipped files;
limitations) are JSONB columns.

Never stored: prompts, diffs or source code, raw provider responses, API keys, GitHub or OAuth
tokens, and request headers.
