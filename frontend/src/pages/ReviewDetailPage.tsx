import { Link, useLocation, useParams } from 'react-router';
import { isMissingResource } from '../api/errors.ts';
import { getReview } from '../api/reviews.ts';
import { Button } from '../components/Button.tsx';
import { buttonClassName } from '../components/buttonClassName.ts';
import { EmptyState } from '../components/EmptyState.tsx';
import { ErrorPanel } from '../components/ErrorPanel.tsx';
import { Icon } from '../components/Icon.tsx';
import { Spinner } from '../components/Spinner.tsx';
import { ReviewPending } from '../features/reviews/ReviewPending.tsx';
import { ReviewView } from '../features/reviews/ReviewView.tsx';
import { useStartReview, type ReviewLocationState } from '../features/reviews/useStartReview.ts';
import { useAsync } from '../hooks/useAsync.ts';
import type { StoredReview } from '../types/api.ts';
import styles from './Pages.module.css';

export default function ReviewDetailPage() {
  const { reviewId = '' } = useParams();
  const location = useLocation();
  // Right after POST /api/reviews/github the response is passed in router state, so the page
  // can show it immediately (including whether it came from cache) without refetching.
  const run = (location.state as ReviewLocationState | null)?.run;
  const fromRun = run?.id === reviewId ? run : undefined;

  const loaded = useAsync((signal) => getReview(reviewId, signal), reviewId, {
    enabled: !fromRun,
  });
  const rerun = useStartReview();

  let stored: StoredReview | undefined = fromRun;
  if (!stored && loaded.status === 'success') stored = loaded.data;

  if (!stored) {
    if (loaded.status === 'error') {
      return isMissingResource(loaded.error) ? (
        <>
          <title>Review not found — RepoPilot</title>
          <EmptyState
            icon="search"
            titleAs="h1"
            title="Review not found"
            action={
              <Link to="/reviews" className={buttonClassName('secondary')}>
                Browse review history
              </Link>
            }
          >
            No stored review has this ID. It may have been mistyped.
          </EmptyState>
        </>
      ) : (
        <>
          <title>Review unavailable — RepoPilot</title>
          <h1 className="visually-hidden">Review unavailable</h1>
          <ErrorPanel error={loaded.error} onRetry={loaded.retry} />
        </>
      );
    }
    return (
      <div className={styles.loadingPage}>
        <Spinner size={20} label="Loading review" />
        <span>Loading review…</span>
      </div>
    );
  }

  const pr = stored.review.pull_request;
  const target = { owner: pr.owner, repo: pr.repo, pullNumber: pr.number };

  return (
    <>
      <title>{`${pr.owner}/${pr.repo}#${pr.number} review — RepoPilot`}</title>
      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <Link to="/reviews">
          <Icon name="arrowLeft" size={14} /> Review history
        </Link>
      </nav>
      <ReviewView
        stored={stored}
        cached={fromRun?.cached}
        actions={
          <>
            <Button
              icon={<Icon name="refresh" size={14} />}
              loading={rerun.pending !== null}
              onClick={() => void rerun.start(target, { force: true })}
            >
              {rerun.pending ? 'Running review…' : 'Run review again'}
            </Button>
            <span className={styles.actionNote}>
              Always runs a new AI review of the PR&apos;s current commit, even if a stored one
              exists.
            </span>
          </>
        }
        notice={
          rerun.pending ? (
            <ReviewPending pr={rerun.pending} force />
          ) : (
            rerun.error !== null && (
              <ErrorPanel
                error={rerun.error}
                onRetry={() => void rerun.start(target, { force: true })}
              />
            )
          )
        }
      />
    </>
  );
}
