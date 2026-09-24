import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client.ts';
import { createReview, getReview } from '../api/reviews.ts';
import { deferred, makeRun, makeStored } from '../test/fixtures.ts';
import { renderApp } from '../test/renderApp.tsx';
import type { ReviewRunResponse } from '../types/api.ts';

vi.mock('../api/reviews.ts');

const ID = '11111111-1111-4111-8111-111111111111';
const NEW_ID = '22222222-2222-4222-8222-222222222222';

beforeEach(() => {
  vi.resetAllMocks();
});

describe('ReviewDetailPage', () => {
  it('loads a stored review by ID', async () => {
    vi.mocked(getReview).mockResolvedValue(makeStored());
    renderApp(`/reviews/${ID}`);

    expect(screen.getByText('Loading review…')).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { level: 1, name: /octo-org\/widgets #42/ }),
    ).toBeInTheDocument();
    expect(getReview).toHaveBeenCalledWith(ID, expect.any(AbortSignal));
    // Loaded by ID: whether it came from cache is unknown, so neither badge is shown.
    expect(screen.queryByText('Cached review')).not.toBeInTheDocument();
    expect(screen.queryByText('New review')).not.toBeInTheDocument();
  });

  it('shows a not-found state for unknown IDs', async () => {
    vi.mocked(getReview).mockRejectedValue(new ApiError(404, 'Review not found.'));
    renderApp(`/reviews/${ID}`);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Review not found' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Browse review history' })).toHaveAttribute(
      'href',
      '/reviews',
    );
  });

  it('treats a malformed review ID as not found', async () => {
    vi.mocked(getReview).mockRejectedValue(new ApiError(422, null));
    renderApp('/reviews/not-a-uuid');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Review not found' }),
    ).toBeInTheDocument();
  });

  it('shows other failures with a retry', async () => {
    vi.mocked(getReview)
      .mockRejectedValueOnce(new ApiError(503, 'Review storage is unavailable.'))
      .mockResolvedValueOnce(makeStored());
    const { user } = renderApp(`/reviews/${ID}`);

    expect(await screen.findByRole('alert')).toHaveTextContent('Review storage is unavailable.');
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('High risk')).toBeInTheDocument();
  });

  it('uses the POST response from navigation state without refetching', () => {
    renderApp(`/reviews/${ID}`, { run: makeRun({ cached: false }) });

    expect(screen.getByText('New review')).toBeInTheDocument();
    expect(getReview).not.toHaveBeenCalled();
  });

  it('re-runs with force=true, disables the button while pending, then shows the new review', async () => {
    vi.mocked(getReview).mockResolvedValue(makeStored());
    const rerun = deferred<ReviewRunResponse>();
    vi.mocked(createReview).mockReturnValue(rerun.promise);
    const { user } = renderApp(`/reviews/${ID}`);

    await user.click(await screen.findByRole('button', { name: 'Run review again' }));

    expect(createReview).toHaveBeenCalledWith(
      { owner: 'octo-org', repo: 'widgets', pullNumber: 42 },
      { force: true, signal: expect.any(AbortSignal) },
    );
    const button = screen.getByRole('button', { name: /Running review/ });
    expect(button).toBeDisabled();
    expect(screen.getByText('Running a new review…')).toBeInTheDocument();

    rerun.resolve(makeRun({ id: NEW_ID, cached: false }, { summary: 'Fresh summary.' }));

    expect(await screen.findByText('Fresh summary.')).toBeInTheDocument();
    expect(screen.getByText('New review')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run review again' })).toBeEnabled();
    expect(createReview).toHaveBeenCalledTimes(1);
  });

  it('shows re-run failures without losing the current review', async () => {
    vi.mocked(getReview).mockResolvedValue(makeStored());
    vi.mocked(createReview).mockRejectedValue(
      new ApiError(504, 'The AI provider did not respond in time.'),
    );
    const { user } = renderApp(`/reviews/${ID}`);

    await user.click(await screen.findByRole('button', { name: 'Run review again' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Review timed out');
    expect(screen.getByText('High risk')).toBeInTheDocument();
  });
});
