import { Link } from 'react-router';
import { Badge } from '../../components/Badge.tsx';
import type { ReviewSummary } from '../../types/api.ts';
import { formatDateTime, shortSha } from '../../utils/format.ts';
import { RiskLabel } from './RiskIndicator.tsx';
import { reviewPath } from './useStartReview.ts';
import styles from './ReviewHistoryTable.module.css';

interface ReviewHistoryTableProps {
  reviews: ReviewSummary[];
  caption: string;
}

/** Table on wide screens; each row collapses into a card on narrow screens. */
export function ReviewHistoryTable({ reviews, caption }: ReviewHistoryTableProps) {
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Pull request</th>
            <th scope="col">Risk</th>
            <th scope="col">Findings</th>
            <th scope="col">Model</th>
            <th scope="col">Reviewed</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => (
            <tr key={review.id}>
              <td className={styles.prCell}>
                <Link to={reviewPath(review.id)} className={styles.prLink}>
                  <span className={styles.repo}>
                    {review.owner}/{review.repo}
                  </span>{' '}
                  <span className={styles.number}>#{review.pull_number}</span>
                </Link>
                <code className={styles.sha} title={review.head_sha}>
                  {shortSha(review.head_sha)}
                </code>
              </td>
              <td data-label="Risk">
                <RiskLabel level={review.risk_level} />
              </td>
              <td data-label="Findings" className={styles.count}>
                {review.finding_count}
              </td>
              <td data-label="Model">
                <code className={styles.model}>{review.model}</code>
              </td>
              <td data-label="Reviewed" className={styles.date}>
                <time dateTime={review.created_at}>{formatDateTime(review.created_at)}</time>
              </td>
              <td data-label="Status">
                {review.is_current ? (
                  <Badge>Current</Badge>
                ) : (
                  <Badge tone="warning">Superseded</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
