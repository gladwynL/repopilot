# RepoPilot: portfolio notes

A reference for describing RepoPilot on a resume or in an interview. Everything here describes
implemented, tested behavior. Nothing has been deployed publicly, and no review has run against
the live OpenAI API yet (development used mocked responses).

## Resume bullets

- Built **RepoPilot**, an AI-assisted GitHub pull request reviewer (**FastAPI, React/TypeScript,
  PostgreSQL**). It turns PR diffs into schema-validated LLM findings (OpenAI Responses API with
  strict structured outputs and Pydantic) and drops any file or line reference the supplied
  diff can't support.
- Designed deterministic **large-PR handling**: file ranking, token-budget estimation, per-file
  truncation, and chunking, with code-based merging and deduplication of results. Added
  **cache-aware persistence** keyed by commit SHA, model, prompt version, and budget settings,
  so unchanged PRs never trigger a second paid model call. Concurrency is enforced by a partial
  unique index and advisory locks.
- Shipped **production infrastructure**: GitHub OAuth sign-in (state + PKCE) with an
  allowlist, non-root Docker images behind Caddy on a single HTTPS origin, one-shot Alembic
  migrations, and **GitHub Actions CI**. CI runs 360 backend and frontend tests, including
  PostgreSQL integration and migration checks, plus a production-stack smoke test.

## 30-second version

RepoPilot reviews GitHub pull requests with an LLM. You give it a PR, and it returns a summary,
a risk level, and specific findings with file and line references, confidence, and suggested
fixes. The interesting part isn't calling a model. It's making the output trustworthy and
affordable: every response is schema-validated, file and line references are checked against
the diff the model actually saw, large PRs are split deterministically within a token budget,
and reviews are cached per commit, so the same code is never paid for twice. It ships with
tests, CI, Docker, and GitHub sign-in.

## 2-minute version

- **Problem.** LLM code review is easy to demo and hard to trust. Models invent line numbers,
  comment on code they never saw, blow past context limits on large PRs, and cost money on
  every call.
- **Architecture.** A FastAPI backend with a thin API layer, services, and repositories. The
  GitHub client normalizes PRs into typed models. The review engine sits behind a provider
  interface (OpenAI first). PostgreSQL stores reviews. A React dashboard is served by Caddy on
  the same HTTPS origin as the API.
- **Hardest problem: bounding and grounding the input.** I rank files deterministically,
  estimate tokens, cut oversized diffs at line boundaries, and pack them into chunks. Each diff
  line is sent with its real line number, and afterwards I throw away any reference the model
  couldn't have seen. Missing GitHub patches become explicit limitations instead of silent
  gaps.
- **LLM reliability.** Strict JSON schema output validated with Pydantic, retries only for
  transient errors, prompts that prefer zero findings to invented ones, and a small evaluation
  framework with per-condition metrics.
- **Persistence and cost.** The cache key covers the commit SHA and every setting that changes
  output. The database guarantees one current review per key, and forced re-runs keep history.
- **Security and delivery.** OAuth with state and PKCE, an allowlist, signed HttpOnly cookies,
  and startup validation of production config. CI covers unit tests, real PostgreSQL
  migrations, the frontend, image contents, and a production Compose smoke test.

## Demo flow

1. Start the stack locally (see the README quick start) and open the dashboard.
2. Paste a PR URL. The form fills in owner, repository, and number, and shows the pending
   state.
3. Open a stored review. Walk through the risk panel, a critical finding with its `file:line`,
   confidence and the "not calibrated" note, test suggestions, and **Coverage & limitations**
   (skipped and truncated files).
4. Show **Run review again** and the superseded entry it leaves in **History**.
5. Show the code behind it: `services/ai/input_builder.py` (budgeting),
   `services/ai/review_engine.py` (grounding and merge), and `repositories/reviews.py`
   (cache concurrency).
6. Show the sign-in gate and the green CI run.

If there's no OpenAI key, use stored reviews and say so: new reviews need a key, and the
pipeline has been tested with mocked model responses.

## Technical challenges

- **GitHub gives incomplete diffs.** Binary and very large files come back with no `patch`.
  Instead of failing or pretending, these files are tracked as "not reviewed" with a reason,
  listed in the prompt so the model knows what it can't see, and shown in the UI.
- **Bounding large PRs.** Relying on the model's context window gives unpredictable cost and
  failures. I built a deterministic input builder (ranking, a conservative `chars / 3` token
  estimate, truncation at line boundaries, first-fit chunking) and merge chunk results in code,
  so the same PR always produces the same prompts.
- **Hallucinated references.** Models cite plausible but wrong lines. The diff is rendered with
  new-file line numbers, and after validation any file or line the model wasn't shown is set
  to `null`. Tests cover invented files, out-of-range lines, and removed lines.
- **Cache races.** Two requests for the same PR can both miss the cache. A partial unique index
  (`cache_key WHERE is_current`) guarantees one current review per key. An early
  retry-on-conflict design failed a six-way concurrency test, so I switched to a per-key
  advisory lock, verified against real PostgreSQL.
- **Production auth without over-building.** GitHub OAuth with state and PKCE, no stored
  tokens, an allowlist re-checked on every request, and signed cookies. Startup validation
  catches missing or unsafe production settings, and its errors name settings without exposing
  secrets.

## Future work

- GitHub App with webhooks: review PRs automatically and post inline comments
- Repository-wide context (full files, call sites) for deeper findings
- Background review jobs with real progress reporting
- A larger labeled evaluation set and calibrated quality metrics
- More LLM providers behind the existing interface
- A hosted public demo once hosting and API spend are approved
