import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Badge } from '../../components/Badge.tsx';
import { Card } from '../../components/Card.tsx';
import { Icon } from '../../components/Icon.tsx';
import type { StoredReview } from '../../types/api.ts';
import { formatDateTime, shortSha } from '../../utils/format.ts';
import { FindingsSection } from './FindingsSection.tsx';
import { pullRequestUrl } from './pullRequestInput.ts';
import { RiskIndicator } from './RiskIndicator.tsx';
import { CoverageSection, SummarySection, TestSuggestionsSection } from './ReviewSections.tsx';
import styles from './ReviewView.module.css';

interface ReviewViewProps {
  stored: StoredReview;
  /** From the POST response; unknown (undefined) when the review was loaded by ID. */
  cached?: boolean;
  /** Extra header content, e.g. the re-run button. */
  actions?: ReactNode;
  /** Shown between the header and the review body, e.g. re-run progress or errors. */
  notice?: ReactNode;
}

/** The single presentation of a review, used for fresh, cached, and historical reviews alike. */
export function ReviewView({ stored, cached, actions, notice }: ReviewViewProps) {
  const { review } = stored;
  const pr = review.pull_request;

  return (
    <div className={styles.view}>
      <Card as="section" className={styles.header} aria-labelledby="review-title">
        <div className={styles.headerMain}>
          <p className={styles.eyebrow}>Pull request review</p>
          <h1 id="review-title" className={styles.title}>
            <a href={pullRequestUrl(pr)} target="_blank" rel="noreferrer">
              <span className={styles.repo}>
                {pr.owner}/{pr.repo}
              </span>{' '}
              <span className={styles.number}>#{pr.number}</span>
              <Icon name="external" size={14} className={styles.externalIcon} />
              <span className="visually-hidden"> (opens GitHub in a new tab)</span>
            </a>
          </h1>

          <div className={styles.badges}>
            {cached === true && (
              <Badge
                tone="success"
                icon={<Icon name="cache" size={12} />}
                title="No new AI request was made."
              >
                Cached review
              </Badge>
            )}
            {cached === false && (
              <Badge tone="info" icon={<Icon name="check" size={12} />}>
                New review
              </Badge>
            )}
            {stored.is_current ? (
              <Badge tone="neutral">Current</Badge>
            ) : (
              <Badge tone="warning" icon={<Icon name="history" size={12} />}>
                Superseded
              </Badge>
            )}
          </div>

          <dl className={styles.facts}>
            <div>
              <dt>Commit</dt>
              <dd>
                <code title={pr.head_sha}>{shortSha(pr.head_sha)}</code>
              </dd>
            </div>
            <div>
              <dt>Reviewed</dt>
              <dd>
                <time dateTime={stored.created_at}>{formatDateTime(stored.created_at)}</time>
              </dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>
                <code>{review.model}</code>
              </dd>
            </div>
            <div>
              <dt>Prompt</dt>
              <dd>
                <code>{review.prompt_version}</code>
              </dd>
            </div>
          </dl>

          {cached === true && (
            <p className={styles.headerNote}>
              This commit was already reviewed with the same model and settings, so the stored
              review was returned without a new AI request.
            </p>
          )}
          {!stored.is_current && (
            <p className={styles.headerNote}>
              A newer review of this commit and configuration exists.{' '}
              <Link
                to={`/reviews?owner=${encodeURIComponent(pr.owner)}&repo=${encodeURIComponent(pr.repo)}&pr=${pr.number}`}
              >
                See all reviews of this pull request
              </Link>
              .
            </p>
          )}
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>
        <div className={styles.headerRisk}>
          <RiskIndicator level={review.risk_level} />
        </div>
      </Card>

      {notice}

      <div className={styles.layout}>
        <div className={styles.primary}>
          <SummarySection summary={review.summary} />
          <FindingsSection
            findings={review.findings}
            reviewedAnything={review.reviewed_files.length > 0}
          />
        </div>
        <aside className={styles.secondary} aria-label="Tests and coverage">
          <TestSuggestionsSection suggestions={review.test_suggestions} />
          <CoverageSection coverage={review} />
        </aside>
      </div>
    </div>
  );
}
