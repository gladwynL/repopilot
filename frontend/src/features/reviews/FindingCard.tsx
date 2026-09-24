import { Badge } from '../../components/Badge.tsx';
import { Icon } from '../../components/Icon.tsx';
import type { ReviewFinding } from '../../types/api.ts';
import { formatConfidence, formatFileReference } from '../../utils/format.ts';
import { CATEGORY_LABEL, SEVERITY_LABEL, SEVERITY_TONE } from './labels.ts';
import { LevelGlyph } from './LevelGlyph.tsx';
import styles from './FindingCard.module.css';
import { RichText } from '../../components/RichText.tsx';

export const CONFIDENCE_HELP =
  "The model's own confidence in this finding. It is not a calibrated probability or a guarantee.";

export function FindingCard({ finding }: { finding: ReviewFinding }) {
  return (
    <article className={`${styles.card} ${styles[finding.severity]}`}>
      <header className={styles.meta}>
        <Badge
          tone={SEVERITY_TONE[finding.severity]}
          icon={<LevelGlyph level={finding.severity} />}
        >
          {SEVERITY_LABEL[finding.severity]}
        </Badge>
        <Badge>{CATEGORY_LABEL[finding.category]}</Badge>
        <span className={styles.confidence} title={CONFIDENCE_HELP}>
          {formatConfidence(finding.confidence)} confidence
        </span>
      </header>

      <h3 className={styles.title}>{finding.title}</h3>
      <p className={styles.description}>
        <RichText text={finding.description} />
      </p>

      <div className={styles.suggestion}>
        <p className={styles.suggestionLabel}>Suggested fix</p>
        <p>
          <RichText text={finding.suggestion} />
        </p>
      </div>

      <footer className={styles.location}>
        <Icon name="file" size={14} />
        {finding.file ? (
          <code className={styles.path}>
            {formatFileReference(finding.file, finding.line_start, finding.line_end)}
          </code>
        ) : (
          <span className={styles.noFile}>Applies to the pull request as a whole</span>
        )}
      </footer>
    </article>
  );
}
