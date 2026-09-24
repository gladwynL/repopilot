import type { RiskLevel } from '../../types/api.ts';
import { NOT_ASSESSED_DESCRIPTION, RISK_DESCRIPTION, SEVERITY_LABEL } from './labels.ts';
import styles from './RiskIndicator.module.css';
import { LevelGlyph } from './LevelGlyph.tsx';

interface RiskIndicatorProps {
  level: RiskLevel | null;
}

/** Prominent "AI-assessed risk" block: glyph + word + explanation, never color alone. */
export function RiskIndicator({ level }: RiskIndicatorProps) {
  const label = level ? `${SEVERITY_LABEL[level]} risk` : 'Not assessed';
  return (
    <div className={`${styles.risk} ${styles[level ?? 'none']}`}>
      <LevelGlyph level={level} className={styles.glyph} />
      <div>
        <p className={styles.caption}>AI-assessed risk</p>
        <p className={styles.label}>{label}</p>
        <p className={styles.description}>
          {level ? RISK_DESCRIPTION[level] : NOT_ASSESSED_DESCRIPTION}
        </p>
      </div>
    </div>
  );
}

/** Compact risk label for tables and lists. */
export function RiskLabel({ level }: RiskIndicatorProps) {
  return (
    <span className={`${styles.inline} ${styles[level ?? 'none']}`}>
      <LevelGlyph level={level} />
      {level ? SEVERITY_LABEL[level] : 'Not assessed'}
    </span>
  );
}
