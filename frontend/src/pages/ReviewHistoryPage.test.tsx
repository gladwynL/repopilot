import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client.ts';
import { listReviews } from '../api/reviews.ts';
import { deferred, makePage, makeSummary } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import type { ReviewHistoryPage } from '../types/api.ts';

vi.mock('../api/reviews.ts');

beforeEach(() => {
  vi.resetAllMocks();
});

const summaries = (count: number, start = 0) =>
  Array.from({ length: count }, (_, i) =>
    makeSummary({
      id: `00000000-0000-4000-8000-${String(start + i).padStart(12, '0')}`,
      pull_number: start + i + 1,
    }),
  );

describe('ReviewHistoryPage', () => {
  it('shows a loading state, then the list', async () => {
    const request = deferred<ReviewHistoryPage>();
    vi.mocked(listReviews).mockReturnValue(request.promise);
    renderApp('/reviews');

    expect(screen.getByText('Loading review history…')).toBeInTheDocument();

    request.resolve(makePage([makeSummary({ risk_level: null, is_current: false })]));
    const table = await screen.findByRole('table', { name: 'Stored reviews' });
    const row = within(table).getAllByRole('row')[1];
    expect(within(row).getByRole('link')).toHaveAttribute(
      'href',
      '/reviews/11111111-1111-4111-8111-111111111111',
    );
    expect(within(row).getByText('Not assessed')).toBeInTheDocument();
    expect(within(row).getByText('3')).toBeInTheDocument();
    expect(within(row).getByText('gpt-5.6-terra')).toBeInTheDocument();
    expect(within(row).getByText('Superseded')).toBeInTheDocument();
  });

  it('shows an empty state with a call to action', async () => {
    vi.mocked(listReviews).mockResolvedValue(makePage([]));
    renderApp('/reviews');

    expect(await screen.findByText('No reviews yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review a pull request' })).toHaveAttribute(
      'href',
      '/',
    );
  });

  it('paginates with limit and offset', async () => {
    vi.mocked(listReviews)
      .mockResolvedValueOnce(makePage(summaries(20), { total: 25 }))
      .mockResolvedValueOnce(makePage(summaries(5, 20), { total: 25, offset: 20 }));
    const { user } = renderApp('/reviews');

    expect(await screen.findByText('Showing 1–20 of 25')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('Showing 21–25 of 25')).toBeInTheDocument();
    expect(listReviews).toHaveBeenLastCalledWith(
      { owner: undefined, repo: undefined, pullNumber: undefined, limit: 20, offset: 20 },
      expect.any(AbortSignal),
    );
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });

  it('applies filters through the URL', async () => {
    vi.mocked(listReviews).mockResolvedValue(makePage([]));
    const { user } = renderApp('/reviews');
    await screen.findByText('No reviews yet');

    await user.type(screen.getByLabelText('Owner'), 'octo-org');
    await user.type(screen.getByLabelText('PR number'), '42');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    expect(await screen.findByText('No matching reviews')).toBeInTheDocument();
    expect(listReviews).toHaveBeenLastCalledWith(
      { owner: 'octo-org', repo: undefined, pullNumber: 42, limit: 20, offset: 0 },
      expect.any(AbortSignal),
    );
  });

  it('rejects invalid filter values without calling the API', async () => {
    vi.mocked(listReviews).mockResolvedValue(makePage([]));
    const { user } = renderApp('/reviews');
    await screen.findByText('No reviews yet');

    await user.type(screen.getByLabelText('PR number'), 'abc');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    expect(screen.getByLabelText('PR number')).toHaveAttribute('aria-invalid', 'true');
    expect(listReviews).toHaveBeenCalledTimes(1);
  });

  it('handles invalid filters in the URL', () => {
    renderApp('/reviews?pr=abc');

    expect(screen.getByText('Invalid filters')).toBeInTheDocument();
    expect(listReviews).not.toHaveBeenCalled();
  });

  it('shows API errors with a retry', async () => {
    vi.mocked(listReviews)
      .mockRejectedValueOnce(new ApiError(503, 'Review storage is unavailable.'))
      .mockResolvedValueOnce(makePage([makeSummary()]));
    const { user } = renderApp('/reviews');

    expect(await screen.findByRole('alert')).toHaveTextContent('Review storage is unavailable.');
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByRole('table', { name: 'Stored reviews' })).toBeInTheDocument();
  });
});
