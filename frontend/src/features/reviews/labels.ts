import type { Tone } from '../../components/Badge.tsx';
import type { FindingCategory, RiskLevel, Severity, SkipReason } from '../../types/api.ts';

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low'];

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

export const SEVERITY_TONE: Record<Severity, Tone> = {
  critical: 'danger',
  high: 'severe',
  medium: 'warning',
  low: 'info',
};

export const CATEGORY_LABEL: Record<FindingCategory, string> = {
  bug: 'Bug',
  security: 'Security',
  reliability: 'Reliability',
  performance: 'Performance',
  maintainability: 'Maintainability',
  code_quality: 'Code quality',
  testing: 'Testing',
};

export const SKIP_REASON_TEXT: Record<SkipReason, string> = {
  no_patch: 'GitHub did not provide a reviewable diff (binary or very large file).',
  generated: 'Generated or vendored file, skipped.',
  over_budget: 'Skipped because the review input limit was reached.',
};

export const RISK_DESCRIPTION: Record<RiskLevel, string> = {
  low: 'No significant problems identified in the reviewed changes.',
  medium: 'Some issues worth addressing before merging.',
  high: 'Likely defects or serious risks in the reviewed changes.',
  critical: 'Severe problems such as security or data-loss risks.',
};

export const NOT_ASSESSED_DESCRIPTION =
  'No diff content could be reviewed, so no risk assessment was made.';
