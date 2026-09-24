import { Link, useSearchParams } from 'react-router';
import { listReviews } from '../api/reviews.ts';
import { Alert } from '../components/Alert.tsx';
import { Button } from '../components/Button.tsx';
import { buttonClassName } from '../components/buttonClassName.ts';
import { Card } from '../components/Card.tsx';
import { EmptyState } from '../components/EmptyState.tsx';
import { ErrorPanel } from '../components/ErrorPanel.tsx';
import { PageHeader } from '../components/PageHeader.tsx';
import { Spinner } from '../components/Spinner.tsx';
import { HistoryFilters } from '../features/reviews/HistoryFilters.tsx';
import {
  validateHistoryFilters,
  type HistoryFilterValues,
} from '../features/reviews/pullRequestInput.ts';
import { ReviewHistoryTable } from '../features/reviews/ReviewHistoryTable.tsx';
import { useAsync } from '../hooks/useAsync.ts';
import styles from './Pages.module.css';

export const PAGE_SIZE = 20;

export default function ReviewHistoryPage() {
  // Filters and page live in the URL so views can be linked, bookmarked, and survive reloads.
  const [params, setParams] = useSearchParams();
  const filters: HistoryFilterValues = {
    owner: params.get('owner') ?? '',
    repo: params.get('repo') ?? '',
    pr: params.get('pr') ?? '',
  };
  const filtersValid = validateHistoryFilters(filters) === null;
  const hasFilters = Boolean(filters.owner || filters.repo || filters.pr);
  const page = Math.max(1, Number.parseInt(params.get('page') ?? '1', 10) || 1);
  const offset = (page - 1) * PAGE_SIZE;

  const history = useAsync(
    (signal) =>
      listReviews(
        {
          owner: filters.owner || undefined,
          repo: filters.repo || undefined,
          pullNumber: filters.pr ? Number(filters.pr) : undefined,
          limit: PAGE_SIZE,
          offset,
        },
        signal,
      ),
    params.toString(),
    { enabled: filtersValid },
  );

  function applyFilters(next: HistoryFilterValues) {
    const nextParams = new URLSearchParams();
    for (const [key, value] of Object.entries(next)) if (value) nextParams.set(key, value);
    setParams(nextParams);
  }

  function goToPage(nextPage: number) {
    const nextParams = new URLSearchParams(params);
    if (nextPage > 1) nextParams.set('page', String(nextPage));
    else nextParams.delete('page');
    setParams(nextParams);
  }

  const clear = () => setParams(new URLSearchParams());

  return (
    <>
      <title>Review history — RepoPilot</title>
      <PageHeader
        title="Review history"
        description="Every stored review, newest first. Re-runs of the same commit are kept; the latest one is marked current."
      />

      <Card className={styles.filterCard}>
        {/* Re-mount when the URL changes (e.g. back/forward) so inputs match the applied filters. */}
        <HistoryFilters
          key={`${filters.owner}|${filters.repo}|${filters.pr}`}
          initial={filters}
          onApply={applyFilters}
          onClear={clear}
        />
      </Card>

      <Card className={styles.resultsCard}>
        {!filtersValid ? (
          <div className={styles.cardPadding}>
            <Alert
              tone="warning"
              title="Invalid filters"
              actions={
                <Button size="sm" onClick={clear}>
                  Clear filters
                </Button>
              }
            >
              This link contains filter values RepoPilot cannot search for.
            </Alert>
          </div>
        ) : history.status === 'loading' ? (
          <div className={styles.loadingRow}>
            <Spinner label="Loading review history" />
            <span>Loading review history…</span>
          </div>
        ) : history.status === 'error' ? (
          <div className={styles.cardPadding}>
            <ErrorPanel error={history.error} onRetry={history.retry} />
          </div>
        ) : history.data.items.length === 0 ? (
          hasFilters || page > 1 ? (
            <EmptyState icon="search" title="No matching reviews">
              {page > 1
                ? 'There are no reviews on this page.'
                : 'No stored reviews match these filters.'}
            </EmptyState>
          ) : (
            <EmptyState
              icon="history"
              title="No reviews yet"
              action={
                <Link to="/" className={buttonClassName('primary')}>
                  Review a pull request
                </Link>
              }
            >
              Completed reviews are stored and listed here.
            </EmptyState>
          )
        ) : (
          <>
            <ReviewHistoryTable reviews={history.data.items} caption="Stored reviews" />
            <nav className={styles.pagination} aria-label="Pagination">
              <p className={styles.pageInfo}>
                Showing {offset + 1}–{offset + history.data.items.length} of {history.data.total}
              </p>
              <div className={styles.pageButtons}>
                <Button size="sm" disabled={page <= 1} onClick={() => goToPage(page - 1)}>
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={offset + history.data.items.length >= history.data.total}
                  onClick={() => goToPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </nav>
          </>
        )}
      </Card>
    </>
  );
}
