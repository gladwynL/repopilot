import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { makeFinding, makeStored } from '../../test/fixtures.ts';
import type { ReviewResult, StoredReview } from '../../types/api.ts';
import { ReviewView } from './ReviewView.tsx';

function renderView(
  result: Partial<ReviewResult> = {},
  stored: Partial<StoredReview> = {},
  cached?: boolean,
) {
  render(
    <MemoryRouter>
      <ReviewView stored={makeStored(stored, result)} cached={cached} />
    </MemoryRouter>,
  );
}

const section = (name: string) => screen.getByRole('region', { name: new RegExp(name) });

describe('ReviewView', () => {
  it('renders the header, summary and AI-assessed risk', () => {
    renderView();

    const title = screen.getByRole('heading', { level: 1, name: /octo-org\/widgets #42/ });
    expect(within(title).getByRole('link')).toHaveAttribute(
      'href',
      'https://github.com/octo-org/widgets/pull/42',
    );
    expect(screen.getByText('AI-assessed risk')).toBeInTheDocument();
    expect(screen.getByText('High risk')).toBeInTheDocument();
    expect(screen.getByText('abcdef1')).toBeInTheDocument();
    expect(screen.getByText('gpt-5.6-terra')).toBeInTheDocument();
    expect(within(section('Summary')).getByText(/off-by-one/)).toBeInTheDocument();
  });

  it('shows "Not assessed" when no risk level was produced', () => {
    renderView({ risk_level: null, findings: [], reviewed_files: [] });

    expect(screen.getByText('Not assessed')).toBeInTheDocument();
    expect(screen.queryByText(/Low risk/)).not.toBeInTheDocument();
    expect(screen.getByText('Nothing to review')).toBeInTheDocument();
    expect(screen.getByText('No file contents were reviewed.')).toBeInTheDocument();
  });

  it('renders a finding with severity, category, confidence and location', () => {
    renderView({ findings: [makeFinding({ line_start: 42, line_end: 48 })] });

    const finding = within(section('Findings')).getByRole('article');
    expect(within(finding).getByText('High')).toBeInTheDocument();
    expect(within(finding).getByText('Bug')).toBeInTheDocument();
    expect(within(finding).getByText('93% confidence')).toBeInTheDocument();
    expect(
      within(finding).getByRole('heading', { name: 'Index out of range in last_item' }),
    ).toBeInTheDocument();
    expect(within(finding).getByText(/raises IndexError/)).toBeInTheDocument();
    expect(within(finding).getByText(/handle empty input/)).toBeInTheDocument();
    expect(within(finding).getByText('src/collections_util.py:42–48')).toBeInTheDocument();
  });

  it('renders backtick spans in model text as inline code, never as HTML', () => {
    renderView({
      findings: [makeFinding({ description: 'Calls `create_charge` twice. <b>bold</b>' })],
    });

    const code = screen.getByText('create_charge');
    expect(code.tagName).toBe('CODE');
    expect(screen.getByText('twice. <b>bold</b>', { exact: false })).toBeInTheDocument();
    expect(document.querySelector('b')).toBeNull();
  });

  it('shows PR-wide findings without inventing a location', () => {
    renderView({ findings: [makeFinding({ file: null, line_start: null })] });

    expect(screen.getByText('Applies to the pull request as a whole')).toBeInTheDocument();
  });

  it('shows an empty state when there are no findings', () => {
    renderView({ findings: [] });

    expect(within(section('Findings')).getByText('No findings')).toBeInTheDocument();
  });

  it('filters findings by severity and category, preserving backend order', async () => {
    const user = userEvent.setup();
    renderView({
      findings: [
        makeFinding({ title: 'Critical bug', severity: 'critical' }),
        makeFinding({ title: 'Security issue', severity: 'high', category: 'security' }),
        makeFinding({ title: 'Minor bug', severity: 'low' }),
      ],
    });
    const findings = section('Findings');
    const titles = () =>
      within(findings)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent);

    expect(titles()).toEqual(['Critical bug', 'Security issue', 'Minor bug']);
    await user.selectOptions(within(findings).getByLabelText('Category'), 'bug');
    expect(titles()).toEqual(['Critical bug', 'Minor bug']);
    await user.selectOptions(within(findings).getByLabelText('Severity'), 'low');
    expect(titles()).toEqual(['Minor bug']);
    await user.click(within(findings).getByRole('button', { name: 'Clear filters' }));
    expect(titles()).toHaveLength(3);
  });

  it('lists test suggestions, or an empty state', () => {
    renderView();
    const tests = section('Test suggestions');
    expect(within(tests).getByText('Cover empty and single-item lists.')).toBeInTheDocument();
    expect(within(tests).getByText('tests/test_util.py')).toBeInTheDocument();
  });

  it('shows the empty test-suggestion state', () => {
    renderView({ test_suggestions: [] });

    expect(screen.getByText('No additional test suggestions.')).toBeInTheDocument();
  });

  it('explains skipped and truncated files and limitations', () => {
    renderView({
      reviewed_files: ['src/app.py', 'src/big.py'],
      truncated_files: ['src/big.py'],
      skipped_files: [
        { filename: 'logo.png', reason: 'no_patch' },
        { filename: 'yarn.lock', reason: 'generated' },
        { filename: 'src/extra.py', reason: 'over_budget' },
      ],
      limitations: ['The PR was reviewed in 2 separate parts.'],
    });

    const coverage = section('Coverage');
    expect(
      within(coverage).getByText('The PR was reviewed in 2 separate parts.'),
    ).toBeInTheDocument();
    expect(
      within(coverage).getByText(/GitHub did not provide a reviewable diff/),
    ).toBeInTheDocument();
    expect(within(coverage).getByText(/Generated or vendored file/)).toBeInTheDocument();
    expect(within(coverage).getByText(/review input limit was reached/)).toBeInTheDocument();
    expect(within(coverage).getByText(/Partially reviewed/)).toBeInTheDocument();
  });

  it('says so when coverage was complete', () => {
    renderView();

    expect(screen.getByText(/Every changed file was reviewed in full/)).toBeInTheDocument();
  });

  it('marks cached and new reviews', () => {
    renderView({}, {}, true);
    expect(screen.getByText('Cached review')).toBeInTheDocument();
    expect(screen.getByText(/without a new AI request/)).toBeInTheDocument();
  });

  it('marks a freshly generated review', () => {
    renderView({}, {}, false);

    expect(screen.getByText('New review')).toBeInTheDocument();
    expect(screen.queryByText('Cached review')).not.toBeInTheDocument();
  });

  it('marks superseded historical reviews and links to the PR history', () => {
    renderView({}, { is_current: false });

    expect(screen.getByText('Superseded')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /See all reviews of this pull request/ }),
    ).toHaveAttribute('href', '/reviews?owner=octo-org&repo=widgets&pr=42');
  });
});
