import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { listReviews } from './api/reviews.ts';
import { makePage } from './test/fixtures.ts';
import { renderApp } from './test/renderApp.tsx';

vi.mock('./api/reviews.ts');

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listReviews).mockResolvedValue(makePage([]));
});

describe('App shell', () => {
  it('shows the RepoPilot brand and main navigation', () => {
    renderApp('/');

    expect(screen.getByRole('link', { name: 'RepoPilot dashboard' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(nav).toHaveTextContent('Dashboard');
    expect(nav).toHaveTextContent('History');
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('navigates between dashboard and history', async () => {
    const { user } = renderApp('/');

    await user.click(screen.getByRole('link', { name: 'History' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Review history' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page');

    await user.click(screen.getByRole('link', { name: 'Dashboard' }));
    expect(
      screen.getByRole('heading', { level: 1, name: 'Review a pull request' }),
    ).toBeInTheDocument();
  });

  it('shows a 404 page for unknown routes', () => {
    renderApp('/does/not/exist');

    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to the dashboard' })).toHaveAttribute('href', '/');
  });
});
