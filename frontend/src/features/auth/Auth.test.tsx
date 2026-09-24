import { act, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { logout } from '../../api/auth.ts';
import { ApiError, UNAUTHORIZED_EVENT } from '../../api/client.ts';
import { toUserFacingError } from '../../api/errors.ts';
import { listReviews } from '../../api/reviews.ts';
import { deferred, makePage } from '../../test/fixtures.ts';
import { renderApp } from '../../test/renderApp.tsx';
import type { AuthStatus } from '../../types/api.ts';

vi.mock('../../api/reviews.ts');
vi.mock('../../api/auth.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/auth.ts')>()),
  logout: vi.fn(),
}));

const SIGNED_OUT: AuthStatus = { auth_enabled: true, user: null };
const SIGNED_IN: AuthStatus = {
  auth_enabled: true,
  user: { login: 'gladwynL', name: 'Gladwyn', avatar_url: 'https://avatars.test/u/1' },
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listReviews).mockResolvedValue(makePage([]));
  vi.mocked(logout).mockResolvedValue(undefined);
});

describe('authentication', () => {
  it('shows the sign-in screen instead of the app when signed out', () => {
    renderApp('/reviews', { auth: SIGNED_OUT });

    expect(
      screen.getByRole('heading', { level: 1, name: 'Sign in to RepoPilot' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();
    expect(listReviews).not.toHaveBeenCalled();
  });

  it('links to the GitHub sign-in, returning to the current page', () => {
    renderApp('/reviews?owner=octo', { auth: SIGNED_OUT });

    expect(screen.getByRole('link', { name: 'Sign in with GitHub' })).toHaveAttribute(
      'href',
      '/api/auth/login?next=%2Freviews%3Fowner%3Docto',
    );
  });

  it.each([
    ['not_allowed', 'This GitHub account is not allowed'],
    ['access_denied', 'Sign-in was cancelled'],
    ['invalid_state', 'Sign-in expired'],
    ['github_error', 'GitHub sign-in failed'],
    ['something-else', 'GitHub sign-in failed'],
  ])('explains the %s sign-in error', (code, title) => {
    renderApp(`/?auth_error=${code}`, { auth: SIGNED_OUT });

    expect(screen.getByText(title)).toBeInTheDocument();
    // The error code is not carried into the next sign-in attempt.
    expect(screen.getByRole('link', { name: 'Sign in with GitHub' })).toHaveAttribute(
      'href',
      '/api/auth/login?next=%2F',
    );
  });

  it('shows the app with the signed-in user', async () => {
    renderApp('/', { auth: SIGNED_IN });

    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByText('gladwynL')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    expect(await screen.findByText('No reviews yet')).toBeInTheDocument();
  });

  it('signs out and returns to the sign-in screen', async () => {
    const { user } = renderApp('/', { auth: SIGNED_IN });

    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    expect(logout).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByRole('heading', { name: 'Sign in to RepoPilot' }),
    ).toBeInTheDocument();
  });

  it('returns to the sign-in screen when the API reports 401', async () => {
    renderApp('/', { auth: SIGNED_IN });
    await screen.findByText('No reviews yet');

    act(() => {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    });

    expect(
      await screen.findByRole('heading', { name: 'Sign in to RepoPilot' }),
    ).toBeInTheDocument();
  });

  it('keeps the app open without sign-in when auth is disabled', async () => {
    renderApp('/', { auth: { auth_enabled: false, user: null } });

    expect(screen.queryByText('Sign in to RepoPilot')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    });
    expect(await screen.findByText('No reviews yet')).toBeInTheDocument();
  });

  it('shows a loading state while the session is checked', async () => {
    const status = deferred<AuthStatus>();
    renderApp('/', { loadAuth: () => status.promise });

    expect(screen.getByRole('status', { name: 'Loading RepoPilot' })).toBeInTheDocument();
    status.resolve(SIGNED_OUT);

    expect(
      await screen.findByRole('heading', { name: 'Sign in to RepoPilot' }),
    ).toBeInTheDocument();
  });

  it('shows a retryable error when the session check fails', async () => {
    const load = vi
      .fn<(signal: AbortSignal) => Promise<AuthStatus>>()
      .mockRejectedValueOnce(new ApiError(0, null))
      .mockResolvedValueOnce(SIGNED_IN);
    const { user } = renderApp('/', { loadAuth: load });

    expect(await screen.findByText('Cannot reach the RepoPilot API')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('gladwynL')).toBeInTheDocument();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('shows a sign-in message for 401 errors from actions', () => {
    expect(toUserFacingError(new ApiError(401, 'Sign in to use RepoPilot.')).title).toBe(
      'Sign in required',
    );
  });
});
