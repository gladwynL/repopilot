import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import App from '../App.tsx';

/** Render the full app (shell + routes) at `path`, like a user opening that URL. */
export function renderApp(path = '/', state?: unknown) {
  const user = userEvent.setup();
  const result = render(
    <MemoryRouter
      initialEntries={[
        {
          pathname: path.split('?')[0],
          search: path.includes('?') ? `?${path.split('?')[1]}` : '',
          state,
        },
      ]}
    >
      <App />
    </MemoryRouter>,
  );
  return { user, ...result };
}
