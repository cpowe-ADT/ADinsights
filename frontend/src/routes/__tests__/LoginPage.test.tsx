import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import LoginPage from '../LoginPage';

const navigateMock = vi.fn();

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    login: vi.fn(),
    status: 'authenticated',
    error: undefined,
    isAuthenticated: true,
  }),
}));

vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: string; to: string }) => <a href={to}>{children}</a>,
  useLocation: () => ({
    state: {
      from: {
        pathname: '/dashboards/data-sources',
        search: '?code=oauth-code&state=oauth-state',
        hash: '#social',
      },
    },
  }),
  useNavigate: () => navigateMock,
}));

describe('LoginPage', () => {
  it('preserves callback query and hash when redirecting after auth', async () => {
    render(<LoginPage />);

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(
        '/dashboards/data-sources?code=oauth-code&state=oauth-state#social',
        { replace: true },
      );
    });
  });
});
