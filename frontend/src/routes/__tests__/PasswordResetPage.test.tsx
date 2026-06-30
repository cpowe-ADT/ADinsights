import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PasswordResetPage from '../PasswordResetPage';

vi.mock('../../lib/apiClient', () => ({
  __esModule: true,
  default: { post: vi.fn() },
}));

describe('PasswordResetPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders reset password heading in request mode', () => {
    render(
      <MemoryRouter initialEntries={['/password-reset']}>
        <PasswordResetPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Reset your password' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('renders set new password heading in confirm mode', () => {
    render(
      <MemoryRouter initialEntries={['/password-reset?token=abc123']}>
        <PasswordResetPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Set a new password' })).toBeInTheDocument();
    expect(screen.getByLabelText('New password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument();
  });

  it('has return to sign in link', () => {
    render(
      <MemoryRouter initialEntries={['/password-reset']}>
        <PasswordResetPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Return to sign in' })).toBeInTheDocument();
  });
});
