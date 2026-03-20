import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportsPage from '../ReportsPage';

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

const phase2ApiMock = vi.hoisted(() => ({
  listReports: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

vi.mock('../../lib/phase2Api', () => ({
  listReports: phase2ApiMock.listReports,
}));

describe('ReportsPage', () => {
  beforeEach(() => {
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    phase2ApiMock.listReports.mockResolvedValue([]);
  });

  it('shows the new report action for non-viewer users', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listReports).toHaveBeenCalled());
    expect(screen.getByRole('link', { name: /new report/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create report/i })).toBeInTheDocument();
  });

  it('hides report creation actions for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listReports).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: /new report/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create report/i })).not.toBeInTheDocument();
  });
});
