# Roadmap

RepoPilot was built in seven phases; all are complete.

| Phase | Delivered |
| --- | --- |
| 0. Foundation | FastAPI + React/Vite skeleton, PostgreSQL via Compose, pytest/Vitest, Ruff/ESLint/Prettier |
| 1. GitHub ingestion | Async read-only GitHub client with pagination; normalized `PullRequest` model; upstream errors mapped to API errors |
| 2. AI review engine | Deterministic input budgeting and chunking, versioned prompts, OpenAI structured outputs, diff-grounded findings, code-based merging |
| 3. Persistence and evaluation | PostgreSQL review history, cache keyed by commit and config, forced re-runs, evaluation runner and CLI, real-database integration tests |
| 4. Dashboard | React dashboard: review form, honest pending state, review view, filterable history, responsive light/dark UI |
| 5. Production readiness | GitHub OAuth + allowlist, startup config validation, Docker images, Caddy, production Compose with migrations, GitHub Actions CI |
| 6. Portfolio polish | README, screenshots, architecture diagrams, API and engine docs, portfolio notes |

## Design decisions worth knowing

- **One HTTPS origin** (Caddy serves the SPA and proxies `/api`): no production CORS, and
  session cookies stay first-party.
- **Deterministic review input**: the same PR and configuration always produce the same prompts,
  which makes caching and debugging trustworthy.
- **Grounding over trust**: file and line references the supplied diff can't support are
  removed, and the model is told to prefer zero findings to speculative ones.
- **Cache identity** includes everything that changes a review's content (commit SHA, model,
  prompt version, budgets) and nothing that doesn't (timeouts, retries).
- **Migrations are a deliberate step** (a one-shot `migrate` service), never run by API
  processes at startup.

## Known limitations

- **No live validation yet.** There is no public deployment, and the pipeline and evaluation
  suite have not been run against the live OpenAI API (tests use mocked responses).
- **Review scope.** Only diffs are reviewed, not full files. Chunks are reviewed independently,
  so cross-chunk issues can be missed, and multi-chunk summaries are joined rather than
  rewritten. Findings about removed code carry no line number.
- **Tokens are estimated** (`ceil(chars / 3)`), not counted with the model's tokenizer.
- **Cost under races.** Concurrent uncached requests for the same PR each pay for a model call
  (both results are stored, one becomes current). If the database fails after a successful
  model call, that review is lost.
- **Sessions** are stateless signed cookies. They can't be revoked individually; remove the
  login from the allowlist or rotate `SESSION_SECRET`.
- **The review concurrency cap is per process**, not global.
- **Operations.** History uses offset pagination, there is no retention policy, and VPS
  backups and schema rollback are manual.
- **GitHub caps** the files it lists at 3,000 per PR, and `patch` is absent for binary or very
  large files.

## Waiting on external access

- A public deployment needs a server or hosting account, a domain, a GitHub OAuth App, and
  approval for the spending. Everything else is ready (see [deployment.md](deployment.md)).
- A live review and the evaluation suite need an `OPENAI_API_KEY` and a small approved budget.

## Possible future work

See [portfolio.md](portfolio.md#future-work).
