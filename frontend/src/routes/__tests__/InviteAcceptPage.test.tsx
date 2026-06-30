import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import InviteAcceptPage from '../InviteAcceptPage';

vi.mock('../../lib/apiClient', () => ({
  __esModule: true,
  default: { post: vi.fn() },
}));

describe('InviteAcceptPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders accept invite heading', () => {
    render(
      <MemoryRouter initialEntries={['/accept-invite?token=abc123']}>
        <InviteAcceptPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Accept invite' })).toBeInTheDocument();
  });

  it('renders form fields for name and password', () => {
    render(
      <MemoryRouter initialEntries={['/accept-invite?token=abc123']}>
        <InviteAcceptPage />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText('First name')).toBeInTheDocument();
    expect(screen.getByLabelText('Last name')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm password')).toBeInTheDocument();
  });

  it('has activate account button', () => {
    render(
      <MemoryRouter initialEntries={['/accept-invite?token=abc123']}>
        <InviteAcceptPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: 'Activate account' })).toBeInTheDocument();
  });
});
