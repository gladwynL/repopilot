import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ReviewForm } from './ReviewForm.tsx';

function setup(pending = false) {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(<ReviewForm onSubmit={onSubmit} pending={pending} />);
  return { onSubmit, user };
}

describe('ReviewForm', () => {
  it('renders labelled inputs', () => {
    setup();

    expect(screen.getByLabelText('Pull request URL')).toBeInTheDocument();
    expect(screen.getByLabelText('Owner')).toBeInTheDocument();
    expect(screen.getByLabelText('Repository')).toBeInTheDocument();
    expect(screen.getByLabelText('PR number')).toBeInTheDocument();
  });

  it('shows errors for required fields and does not submit', async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByRole('button', { name: 'Review pull request' }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText('Enter the repository owner.')).toBeInTheDocument();
    expect(screen.getByText('Enter the repository name.')).toBeInTheDocument();
    expect(screen.getByText('Enter the pull request number.')).toBeInTheDocument();
    expect(screen.getByLabelText('Owner')).toHaveAccessibleDescription(
      'Enter the repository owner.',
    );
  });

  it('validates the PR number', async () => {
    const { onSubmit, user } = setup();

    await user.type(screen.getByLabelText('Owner'), 'octo');
    await user.type(screen.getByLabelText('Repository'), 'app');
    await user.type(screen.getByLabelText('PR number'), '0');
    await user.click(screen.getByRole('button', { name: 'Review pull request' }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText('PR number')).toHaveAttribute('aria-invalid', 'true');
  });

  it('fills the fields from a pasted GitHub PR URL', async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByLabelText('Pull request URL'));
    await user.paste('https://github.com/octo-org/widgets/pull/42/files');

    expect(screen.getByLabelText('Owner')).toHaveValue('octo-org');
    expect(screen.getByLabelText('Repository')).toHaveValue('widgets');
    expect(screen.getByLabelText('PR number')).toHaveValue('42');

    await user.click(screen.getByRole('button', { name: 'Review pull request' }));
    expect(onSubmit).toHaveBeenCalledWith({ owner: 'octo-org', repo: 'widgets', pullNumber: 42 });
  });

  it('flags a malformed URL', async () => {
    const { user } = setup();

    await user.type(
      screen.getByLabelText('Pull request URL'),
      'https://github.com/octo/app/issues/1',
    );

    expect(screen.getByText(/Expected a pull request URL/)).toBeInTheDocument();
  });

  it('disables inputs and the button while pending', () => {
    setup(true);

    expect(screen.getByRole('button', { name: /Reviewing/ })).toBeDisabled();
    expect(screen.getByLabelText('Owner')).toBeDisabled();
  });
});
