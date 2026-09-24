import { useState } from 'react';
import { SectionCard } from '../../components/Card.tsx';
import { EmptyState } from '../../components/EmptyState.tsx';
import { SelectField } from '../../components/Field.tsx';
import { Button } from '../../components/Button.tsx';
import type { FindingCategory, ReviewFinding, Severity } from '../../types/api.ts';
import { CATEGORY_LABEL, SEVERITY_LABEL, SEVERITY_ORDER } from './labels.ts';
import { CONFIDENCE_HELP, FindingCard } from './FindingCard.tsx';
import styles from './ReviewView.module.css';

const ALL = 'all';

interface FindingsSectionProps {
  findings: ReviewFinding[];
  /** False when no file contents were reviewed, so an empty list means nothing. */
  reviewedAnything: boolean;
}

export function FindingsSection({ findings, reviewedAnything }: FindingsSectionProps) {
  const [severity, setSeverity] = useState<Severity | typeof ALL>(ALL);
  const [category, setCategory] = useState<FindingCategory | typeof ALL>(ALL);

  // Only offer filter values that actually occur, in a stable order.
  const severities = SEVERITY_ORDER.filter((s) => findings.some((f) => f.severity === s));
  const categories = (Object.keys(CATEGORY_LABEL) as FindingCategory[]).filter((c) =>
    findings.some((f) => f.category === c),
  );
  // Backend order (most severe, most confident first) is preserved.
  const visible = findings.filter(
    (f) =>
      (severity === ALL || f.severity === severity) &&
      (category === ALL || f.category === category),
  );
  const filtering = severity !== ALL || category !== ALL;
  const showFilters = findings.length > 1 && (severities.length > 1 || categories.length > 1);

  return (
    <SectionCard
      id="findings-heading"
      title="Findings"
      meta={filtering ? `${visible.length} of ${findings.length}` : findings.length}
    >
      {findings.length === 0 ? (
        reviewedAnything ? (
          <EmptyState icon="check" title="No findings">
            The AI review did not report any issues in the reviewed changes. That is not a guarantee
            the change is correct; check Coverage &amp; limitations for anything that was not
            reviewed.
          </EmptyState>
        ) : (
          <EmptyState icon="info" title="Nothing to review">
            No file contents could be reviewed, so there are no findings. See Coverage &amp;
            limitations for details.
          </EmptyState>
        )
      ) : (
        <>
          {showFilters && (
            <div className={styles.filters}>
              <SelectField
                label="Severity"
                value={severity}
                onChange={(e) => setSeverity(e.target.value as Severity | typeof ALL)}
                options={[
                  { value: ALL, label: 'All severities' },
                  ...severities.map((s) => ({ value: s, label: SEVERITY_LABEL[s] })),
                ]}
              />
              <SelectField
                label="Category"
                value={category}
                onChange={(e) => setCategory(e.target.value as FindingCategory | typeof ALL)}
                options={[
                  { value: ALL, label: 'All categories' },
                  ...categories.map((c) => ({ value: c, label: CATEGORY_LABEL[c] })),
                ]}
              />
              {filtering && (
                <Button
                  variant="ghost"
                  size="sm"
                  className={styles.clearFilters}
                  onClick={() => {
                    setSeverity(ALL);
                    setCategory(ALL);
                  }}
                >
                  Clear filters
                </Button>
              )}
            </div>
          )}
          <p className={styles.help}>{CONFIDENCE_HELP}</p>
          {visible.length === 0 ? (
            <EmptyState compact title="No findings match these filters." />
          ) : (
            <ol className={styles.findingList}>
              {visible.map((finding, index) => (
                <li key={`${finding.file}:${finding.line_start}:${finding.title}:${index}`}>
                  <FindingCard finding={finding} />
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </SectionCard>
  );
}
