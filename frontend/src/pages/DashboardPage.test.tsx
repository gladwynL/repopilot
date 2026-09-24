import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client.ts';
import { createReview, getReview, listReviews } from '../api/reviews.ts';
import { deferred, makePage, makeRun, makeSummary } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import type { ReviewRunResponse } from '../types/api.ts';

vi.mock('../api/reviews.ts');

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listReviews).mockResolvedValue(makePage([]));
});

async function fillAndSubmit(user: ReturnType<typeof renderApp>['user']) {
  await user.type(screen.getByLabelText('Owner'), 'octo-org');
  await user.type(screen.getByLabelText('Repository'), 'widgets');
  await user.type(screen.getByLabelText('PR number'), '42');
  await user.click(screen.getByRole('button', { name: 'Review pull request' }));
}

describe('DashboardPage', () => {
  it('shows the form and an empty recent-reviews state', async () => {
    renderApp('/');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Review a pull request' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('No reviews yet')).toBeInTheDocument();
    expect(listReviews).toHaveBeenCalledWith({ limit: 5, offset: 0 }, expect.any(AbortSignal));
  });

  it('lists recent reviews', async () => {
    vi.mocked(listReviews).mockResolvedValue(makePage([makeSummary()]));
    renderApp('/');

    const table = await screen.findByRole('table', { name: 'Most recent reviews' });
    expect(within(table).getByRole('link', { name: /octo-org\/widgets #42/ })).toHaveAttribute(
      'href',
      '/reviews/11111111-1111-4111-8111-111111111111',
    );
  });

  it('submits, shows an honest pending state, then opens the result', async () => {
    const request = deferred<ReviewRunResponse>();
    vi.mocked(createReview).mockReturnValue(request.promise);
    const { user } = renderApp('/');

    await fillAndSubmit(user);

    expect(createReview).toHaveBeenCalledWith(
      { owner: 'octo-org', repo: 'widgets', pullNumber: 42 },
      { force: false, signal: expect.any(AbortSignal) },
    );
    expect(screen.getByText('Reviewing pull request…')).toBeInTheDocument();
    expect(screen.getByText('What RepoPilot does (not live progress)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reviewing/ })).toBeDisabled();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();

    request.resolve(makeRun({ cached: true }));

    expect(
      await screen.findByRole('heading', { level: 1, name: /octo-org\/widgets #42/ }),
    ).toBeInTheDocument();
    expect(screen.getByText('Cached review')).toBeInTheDocument();
    expect(getReview).not.toHaveBeenCalled(); // the POST response is shown directly
  });

  it('shows a friendly error with the backend message when the review fails', async () => {
    vi.mocked(createReview).mockRejectedValue(
      new ApiError(503, 'AI review is not configured on this server.'),
    );
    const { user } = renderApp('/');

    await fillAndSubmit(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Service unavailable');
    expect(alert).toHaveTextContent('AI review is not configured on this server.');
    expect(screen.getByRole('button', { name: 'Review pull request' })).toBeEnabled();
  });

  it('shows not-found errors for unknown pull requests', async () => {
    vi.mocked(createReview).mockRejectedValue(
      new ApiError(404, 'Repository or pull request not found on GitHub.'),
    );
    const { user } = renderApp('/');

    await fillAndSubmit(user);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Repository or pull request not found on GitHub.',
    );
  });

  it('shows a retryable error when recent reviews fail to load', async () => {
    vi.mocked(listReviews).mockRejectedValueOnce(new ApiError(0, null));
    const { user } = renderApp('/');

    expect(await screen.findByText('Cannot reach the RepoPilot API')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('No reviews yet')).toBeInTheDocument();
    expect(listReviews).toHaveBeenCalledTimes(2);
  });
});
