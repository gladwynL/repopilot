import { render, screen } from '@testing-library/react';
import App from './App.tsx';

it('renders the home page', () => {
  render(<App />);

  expect(screen.getByRole('main')).toBeInTheDocument();
});
