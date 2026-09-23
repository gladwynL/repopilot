import { render, screen } from '@testing-library/react';
import HomePage from './HomePage.tsx';

describe('HomePage', () => {
  it('renders the RepoPilot title', () => {
    render(<HomePage />);

    expect(screen.getByRole('heading', { level: 1, name: 'RepoPilot' })).toBeInTheDocument();
  });

  it('describes the product purpose', () => {
    render(<HomePage />);

    expect(screen.getByText('AI-assisted GitHub pull request review')).toBeInTheDocument();
  });
});
