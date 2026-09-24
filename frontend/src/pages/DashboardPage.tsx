import { Link } from 'react-router';
import { listReviews } from '../api/reviews.ts';
import { buttonClassName } from '../components/buttonClassName.ts';
import { Card, SectionCard } from '../components/Card.tsx';
import { EmptyState } from '../components/EmptyState.tsx';
import { ErrorPanel } from '../components/ErrorPanel.tsx';
import { PageHeader } from '../components/PageHeader.tsx';
import { Spinner } from '../components/Spinner.tsx';
import { ReviewForm } from '../features/reviews/ReviewForm.tsx';
import { ReviewHistoryTable } from '../features/reviews/ReviewHistoryTable.tsx';
import { ReviewPending } from '../features/reviews/ReviewPending.tsx';
import { useStartReview } from '../features/reviews/useStartReview.ts';
import { useAsync } from '../hooks/useAsync.ts';
import styles from './Pages.module.css';

const RECENT_LIMIT = 5;

export default function DashboardPage() {
  const { start, pending, error, clearError } = useStartReview();
  const recent = useAsync(
    (signal) => listReviews({ limit: RECENT_LIMIT, offset: 0 }, signal),
    'recent',
  );

  return (
    <>
      <title>RepoPilot — AI Pull Request Review</title>
      <PageHeader
        title="Review a pull request"
        description="AI-assisted review of GitHub pull requests: a summary, an overall risk assessment, findings with file and line references, and test suggestions."
      />

      <div className={styles.stack}>
        <Card className={styles.formCard}>
          <ReviewForm
            pending={pending !== null}
            onSubmit={(pr) => {
              clearError();
              void start(pr);
            }}
          />
        </Card>

        {pending && <ReviewPending pr={pending} />}
        {error !== null && !pending && <ErrorPanel error={error} />}

        <SectionCard
          id="recent-heading"
          title="Recent reviews"
          actions={
            recent.status === 'success' && recent.data.total > RECENT_LIMIT ? (
              <Link to="/reviews" className={buttonClassName('ghost', 'sm')}>
                View all {recent.data.total}
              </Link>
            ) : undefined
          }
        >
          {recent.status === 'loading' && (
            <div className={styles.loadingRow}>
              <Spinner label="Loading recent reviews" />
              <span>Loading recent reviews…</span>
            </div>
          )}
          {recent.status === 'error' && <ErrorPanel error={recent.error} onRetry={recent.retry} />}
          {recent.status === 'success' &&
            (recent.data.items.length === 0 ? (
              <EmptyState icon="history" title="No reviews yet">
                Reviews you run are stored and listed here, so you can come back to them later.
              </EmptyState>
            ) : (
              <div className={styles.flushTable}>
                <ReviewHistoryTable reviews={recent.data.items} caption="Most recent reviews" />
              </div>
            ))}
        </SectionCard>
      </div>
    </>
  );
}
