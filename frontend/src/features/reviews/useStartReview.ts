import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { createReview } from '../../api/reviews.ts';
import type { PullRequestRef, ReviewRunResponse } from '../../types/api.ts';

/** Router state passed to the review page so it can show the POST response (incl. `cached`). */
export interface ReviewLocationState {
  run: ReviewRunResponse;
}

export function reviewPath(id: string): string {
  return `/reviews/${id}`;
}

/**
 * Start a review (optionally forced) and open the stored result when it completes.
 * Leaving the page aborts the browser request so a late response cannot navigate away
 * from wherever the user went.
 */
export function useStartReview() {
  const navigate = useNavigate();
  const [pending, setPending] = useState<PullRequestRef | null>(null);
  const [error, setError] = useState<unknown>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const start = useCallback(
    async (pr: PullRequestRef, { force = false }: { force?: boolean } = {}) => {
      if (controllerRef.current) return; // one review request at a time
      const controller = new AbortController();
      controllerRef.current = controller;
      setPending(pr);
      setError(null);
      try {
        const run = await createReview(pr, { force, signal: controller.signal });
        const state: ReviewLocationState = { run };
        navigate(reviewPath(run.id), { state });
      } catch (caught) {
        if (!controller.signal.aborted) setError(caught);
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null;
        if (!controller.signal.aborted) setPending(null);
      }
    },
    [navigate],
  );

  const clearError = useCallback(() => setError(null), []);

  return { start, pending, error, clearError };
}
