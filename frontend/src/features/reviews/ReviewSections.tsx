import { SectionCard } from '../../components/Card.tsx';
import { EmptyState } from '../../components/EmptyState.tsx';
import { Icon } from '../../components/Icon.tsx';
import type { ReviewResult, TestSuggestion } from '../../types/api.ts';
import { pluralize } from '../../utils/format.ts';
import { SKIP_REASON_TEXT } from './labels.ts';
import styles from './ReviewView.module.css';
import { RichText } from '../../components/RichText.tsx';

export function SummarySection({ summary }: { summary: string }) {
  return (
    <SectionCard id="summary-heading" title="Summary">
      <p className={styles.summary}>
        <RichText text={summary} />
      </p>
    </SectionCard>
  );
}

export function TestSuggestionsSection({ suggestions }: { suggestions: TestSuggestion[] }) {
  return (
    <SectionCard id="tests-heading" title="Test suggestions" meta={suggestions.length}>
      {suggestions.length === 0 ? (
        <EmptyState compact icon="check" title="No additional test suggestions." />
      ) : (
        <ul className={styles.plainList}>
          {suggestions.map((suggestion, index) => (
            <li key={`${suggestion.file}:${index}`} className={styles.suggestion}>
              <Icon name="beaker" className={styles.listIcon} />
              <div className={styles.suggestionBody}>
                <p>
                  <RichText text={suggestion.description} />
                </p>
                {suggestion.file && <code className={styles.path}>{suggestion.file}</code>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

type Coverage = Pick<
  ReviewResult,
  'reviewed_files' | 'truncated_files' | 'skipped_files' | 'limitations'
>;

/** What the review did and did not cover. Always shown: hiding gaps would overstate the review. */
export function CoverageSection({ coverage }: { coverage: Coverage }) {
  const { reviewed_files, truncated_files, skipped_files, limitations } = coverage;
  const truncated = new Set(truncated_files);
  const complete =
    skipped_files.length === 0 && truncated_files.length === 0 && limitations.length === 0;

  return (
    <SectionCard
      id="coverage-heading"
      title="Coverage & limitations"
      meta={`${pluralize(reviewed_files.length, 'file')} reviewed`}
    >
      <div className={styles.coverage}>
        {complete && reviewed_files.length > 0 && (
          <EmptyState
            compact
            icon="check"
            title="Every changed file was reviewed in full. No limitations were reported."
          />
        )}
        {reviewed_files.length === 0 && (
          <EmptyState compact icon="info" title="No file contents were reviewed." />
        )}

        {limitations.length > 0 && (
          <div>
            <h3 className={styles.subheading}>Limitations</h3>
            <ul className={styles.bulletList}>
              {limitations.map((limitation) => (
                <li key={limitation}>
                  <RichText text={limitation} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {skipped_files.length > 0 && (
          <div>
            <h3 className={styles.subheading}>Not reviewed ({skipped_files.length})</h3>
            <ul className={styles.fileList}>
              {skipped_files.map((file) => (
                <li key={file.filename}>
                  <code className={styles.path}>{file.filename}</code>
                  <span className={styles.fileNote}>{SKIP_REASON_TEXT[file.reason]}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {reviewed_files.length > 0 && (
          <details className={styles.details} open={reviewed_files.length <= 8}>
            <summary>
              Reviewed files ({reviewed_files.length}
              {truncated.size > 0 ? `, ${truncated.size} partially` : ''})
            </summary>
            <ul className={styles.fileList}>
              {reviewed_files.map((file) => (
                <li key={file}>
                  <code className={styles.path}>{file}</code>
                  {truncated.has(file) && (
                    <span className={styles.fileNote}>
                      Partially reviewed: the diff was cut to fit the review input limit.
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </SectionCard>
  );
}
