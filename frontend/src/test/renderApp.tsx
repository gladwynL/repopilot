import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import App from '../App.tsx';
import { AuthProvider } from '../features/auth/AuthProvider.tsx';
import type { AuthStatus } from '../types/api.ts';

export const AUTH_DISABLED: AuthStatus = { auth_enabled: false, user: null };

interface RenderAppOptions {
  /** Router location state (e.g. the review POST response). */
  state?: unknown;
  /** Known auth status; defaults to auth disabled, like local development. */
  auth?: AuthStatus;
  /** Load the auth status asynchronously instead (exercises the loading/error states). */
  loadAuth?: (signal: AbortSignal) => Promise<AuthStatus>;
}

/** Render the full app (auth gate, shell, routes) at `path`, like a user opening that URL. */
export function renderApp(path = '/', options: RenderAppOptions = {}) {
  const user = userEvent.setup();
  const [pathname, search] = path.split('?');
  const auth = options.loadAuth
    ? { loadStatus: options.loadAuth }
    : { initialStatus: options.auth ?? AUTH_DISABLED };
  const result = render(
    <MemoryRouter
      initialEntries={[{ pathname, search: search ? `?${search}` : '', state: options.state }]}
    >
      <AuthProvider {...auth}>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...result };
}
