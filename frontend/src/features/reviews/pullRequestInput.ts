import type { PullRequestRef } from '../../types/api.ts';

// Same rules as the backend (backend/app/schemas/pull_request.py).
const OWNER_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/;
const REPO_PATTERN = /^[A-Za-z0-9._-]*[A-Za-z0-9][A-Za-z0-9._-]*$/;
const OWNER_MAX_LENGTH = 39;
const REPO_MAX_LENGTH = 100;

export function validateOwner(value: string): string | undefined {
  const owner = value.trim();
  if (!owner) return 'Enter the repository owner.';
  if (owner.length > OWNER_MAX_LENGTH || !OWNER_PATTERN.test(owner)) {
    return 'Use letters, numbers, and single hyphens (not at the start or end).';
  }
  return undefined;
}

export function validateRepo(value: string): string | undefined {
  const repo = value.trim();
  if (!repo) return 'Enter the repository name.';
  if (repo.length > REPO_MAX_LENGTH || !REPO_PATTERN.test(repo)) {
    return 'Use letters, numbers, ".", "-", or "_".';
  }
  return undefined;
}

export function validatePullNumber(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return 'Enter the pull request number.';
  if (!/^\d+$/.test(trimmed) || Number(trimmed) < 1 || !Number.isSafeInteger(Number(trimmed))) {
    return 'Use a positive whole number, e.g. 42.';
  }
  return undefined;
}

export interface PullRequestFormValues {
  owner: string;
  repo: string;
  pullNumber: string;
}

export type PullRequestFormErrors = Partial<Record<keyof PullRequestFormValues, string>>;

export function validatePullRequestForm(
  values: PullRequestFormValues,
): { ok: true; value: PullRequestRef } | { ok: false; errors: PullRequestFormErrors } {
  const errors: PullRequestFormErrors = {
    owner: validateOwner(values.owner),
    repo: validateRepo(values.repo),
    pullNumber: validatePullNumber(values.pullNumber),
  };
  if (errors.owner || errors.repo || errors.pullNumber) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    value: {
      owner: values.owner.trim(),
      repo: values.repo.trim(),
      pullNumber: Number(values.pullNumber.trim()),
    },
  };
}

const PR_URL_PATTERN =
  /^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/\s]+)\/([^/\s]+)\/pull\/(\d+)(?:[/?#].*)?$/i;

/**
 * Parse `https://github.com/owner/repo/pull/123` (optionally with a trailing path such as
 * `/files`, a query, or a fragment). Returns `null` for anything else.
 */
export function parsePullRequestUrl(input: string): PullRequestRef | null {
  const match = PR_URL_PATTERN.exec(input.trim());
  if (!match) return null;
  const [, owner, repo, number] = match;
  const pullNumber = Number(number);
  if (validateOwner(owner) || validateRepo(repo) || pullNumber < 1) return null;
  return { owner, repo, pullNumber };
}

export function pullRequestUrl(pr: { owner: string; repo: string; number: number }): string {
  return `https://github.com/${encodeURIComponent(pr.owner)}/${encodeURIComponent(pr.repo)}/pull/${pr.number}`;
}

export interface HistoryFilterValues {
  owner: string;
  repo: string;
  pr: string;
}

export type HistoryFilterErrors = Partial<Record<keyof HistoryFilterValues, string>>;

/** History filters may be blank; anything entered must be valid for the API. */
export function validateHistoryFilters(filters: HistoryFilterValues): HistoryFilterErrors | null {
  const errors: HistoryFilterErrors = {
    owner: filters.owner ? validateOwner(filters.owner) : undefined,
    repo: filters.repo ? validateRepo(filters.repo) : undefined,
    pr: filters.pr ? validatePullNumber(filters.pr) : undefined,
  };
  return errors.owner || errors.repo || errors.pr ? errors : null;
}
