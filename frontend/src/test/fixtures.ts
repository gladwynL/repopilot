import type {
  ReviewFinding,
  ReviewHistoryPage,
  ReviewResult,
  ReviewRunResponse,
  ReviewSummary,
  StoredReview,
} from '../types/api.ts';

// Test-only fixtures shaped like real API responses.

export function makeFinding(overrides: Partial<ReviewFinding> = {}): ReviewFinding {
  return {
    category: 'bug',
    severity: 'high',
    confidence: 0.934,
    title: 'Index out of range in last_item',
    description: 'items[len(items)] is always one past the end and raises IndexError.',
    suggestion: 'Use items[-1] and handle empty input explicitly.',
    file: 'src/collections_util.py',
    line_start: 42,
    line_end: null,
    ...overrides,
  };
}

export function makeResult(overrides: Partial<ReviewResult> = {}): ReviewResult {
  return {
    pull_request: { owner: 'octo-org', repo: 'widgets', number: 42, head_sha: 'abcdef1234567890' },
    model: 'gpt-5.6-terra',
    prompt_version: '2026-09-23.1',
    summary: 'Simplifies last_item but introduces an off-by-one error.',
    risk_level: 'high',
    findings: [makeFinding()],
    test_suggestions: [
      { description: 'Cover empty and single-item lists.', file: 'tests/test_util.py' },
    ],
    reviewed_files: ['src/collections_util.py'],
    truncated_files: [],
    skipped_files: [],
    limitations: [],
    ...overrides,
  };
}

export function makeStored(
  overrides: Partial<StoredReview> = {},
  result: Partial<ReviewResult> = {},
): StoredReview {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    created_at: '2026-09-23T18:40:12Z',
    is_current: true,
    review: makeResult(result),
    ...overrides,
  };
}

export function makeRun(
  overrides: Partial<ReviewRunResponse> = {},
  result: Partial<ReviewResult> = {},
): ReviewRunResponse {
  return { ...makeStored({}, result), cached: false, ...overrides };
}

export function makeSummary(overrides: Partial<ReviewSummary> = {}): ReviewSummary {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    owner: 'octo-org',
    repo: 'widgets',
    pull_number: 42,
    head_sha: 'abcdef1234567890',
    provider: 'openai',
    model: 'gpt-5.6-terra',
    prompt_version: '2026-09-23.1',
    risk_level: 'medium',
    finding_count: 3,
    is_current: true,
    created_at: '2026-09-23T18:40:12Z',
    ...overrides,
  };
}

export function makePage(
  items: ReviewSummary[],
  overrides: Partial<ReviewHistoryPage> = {},
): ReviewHistoryPage {
  return { items, total: items.length, limit: 20, offset: 0, ...overrides };
}

/** A promise you resolve or reject later, to hold an API call in its pending state. */
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
