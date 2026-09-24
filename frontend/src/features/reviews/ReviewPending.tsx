import { Spinner } from '../../components/Spinner.tsx';
import { useElapsedSeconds } from '../../hooks/useElapsedSeconds.ts';
import type { PullRequestRef } from '../../types/api.ts';
import styles from './ReviewPending.module.css';

const STEPS = [
  'Fetch the pull request and its diff from GitHub',
  'Reuse a stored review if this commit was already reviewed',
  'Otherwise, analyze the changed files',
  'Generate and validate structured review feedback',
];

interface ReviewPendingProps {
  pr: PullRequestRef;
  force?: boolean;
}

/**
 * Honest pending state: the API reports no progress, so this shows elapsed time and a static
 * description of the pipeline rather than a fake progress bar.
 */
export function ReviewPending({ pr, force = false }: ReviewPendingProps) {
  const elapsed = useElapsedSeconds();
  return (
    <div className={styles.pending} role="status" aria-live="polite">
      <div className={styles.header}>
        <Spinner size={18} />
        <div>
          <p className={styles.title}>
            {force ? 'Running a new review…' : 'Reviewing pull request…'}
          </p>
          <p className={styles.target}>
            <code>
              {pr.owner}/{pr.repo}#{pr.pullNumber}
            </code>
            <span aria-hidden="true"> · </span>
            <span>{elapsed}s elapsed</span>
          </p>
        </div>
      </div>
      <div className={styles.steps}>
        <p className={styles.stepsCaption}>What RepoPilot does (not live progress)</p>
        <ol>
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className={styles.note}>
          New AI reviews can take a while, especially for large pull requests. Keep this page open
          until the review appears.
        </p>
      </div>
    </div>
  );
}
