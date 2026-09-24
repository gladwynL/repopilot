// Mirrors backend/app/schemas/review.py (the API contract). Keep the two in sync.

export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type RiskLevel = Severity;
export type FindingCategory =
  | 'bug'
  | 'security'
  | 'reliability'
  | 'performance'
  | 'maintainability'
  | 'code_quality'
  | 'testing';
export type SkipReason = 'no_patch' | 'generated' | 'over_budget';

export interface ReviewFinding {
  category: FindingCategory;
  severity: Severity;
  confidence: number;
  title: string;
  description: string;
  suggestion: string;
  file: string | null;
  line_start: number | null;
  line_end: number | null;
}

export interface TestSuggestion {
  description: string;
  file: string | null;
}

export interface SkippedFile {
  filename: string;
  reason: SkipReason;
}

export interface ReviewedPullRequest {
  owner: string;
  repo: string;
  number: number;
  head_sha: string;
}

export interface ReviewResult {
  pull_request: ReviewedPullRequest;
  model: string;
  prompt_version: string;
  summary: string;
  /** `null` when no diff content could be reviewed. */
  risk_level: RiskLevel | null;
  findings: ReviewFinding[];
  test_suggestions: TestSuggestion[];
  reviewed_files: string[];
  truncated_files: string[];
  skipped_files: SkippedFile[];
  limitations: string[];
}

/** `GET /api/reviews/{id}` */
export interface StoredReview {
  id: string;
  created_at: string;
  is_current: boolean;
  review: ReviewResult;
}

/** `POST /api/reviews/github` */
export interface ReviewRunResponse extends StoredReview {
  cached: boolean;
}

export interface ReviewSummary {
  id: string;
  owner: string;
  repo: string;
  pull_number: number;
  head_sha: string;
  provider: string;
  model: string;
  prompt_version: string;
  risk_level: RiskLevel | null;
  finding_count: number;
  is_current: boolean;
  created_at: string;
}

/** `GET /api/reviews` */
export interface ReviewHistoryPage {
  items: ReviewSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface PullRequestRef {
  owner: string;
  repo: string;
  pullNumber: number;
}

export interface AuthUser {
  login: string;
  name: string | null;
  avatar_url: string | null;
}

/** `GET /api/auth/me` */
export interface AuthStatus {
  auth_enabled: boolean;
  user: AuthUser | null;
}
