import type {
  PullRequestRef,
  ReviewHistoryPage,
  ReviewRunResponse,
  StoredReview,
} from '../types/api.ts';
import { apiRequest } from './client.ts';

export interface CreateReviewOptions {
  /** Run a fresh model review even if a stored one exists for this PR commit. */
  force?: boolean;
  signal?: AbortSignal;
}

export function createReview(
  pr: PullRequestRef,
  { force = false, signal }: CreateReviewOptions = {},
): Promise<ReviewRunResponse> {
  return apiRequest<ReviewRunResponse>('/api/reviews/github', {
    method: 'POST',
    query: force ? { force: true } : undefined,
    body: { owner: pr.owner, repo: pr.repo, pull_number: pr.pullNumber },
    signal,
  });
}

export function getReview(id: string, signal?: AbortSignal): Promise<StoredReview> {
  return apiRequest<StoredReview>(`/api/reviews/${encodeURIComponent(id)}`, { signal });
}

export interface ReviewHistoryQuery {
  owner?: string;
  repo?: string;
  pullNumber?: number;
  limit: number;
  offset: number;
}

export function listReviews(
  query: ReviewHistoryQuery,
  signal?: AbortSignal,
): Promise<ReviewHistoryPage> {
  return apiRequest<ReviewHistoryPage>('/api/reviews', {
    query: {
      owner: query.owner,
      repo: query.repo,
      pull_number: query.pullNumber,
      limit: query.limit,
      offset: query.offset,
    },
    signal,
  });
}
