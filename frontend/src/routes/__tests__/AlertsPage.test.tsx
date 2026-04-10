import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertsPage from '../AlertsPage';

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

const phase2ApiMock = vi.hoisted(() => ({
  listAlerts: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

vi.mock('../../lib/phase2Api', () => ({
  listAlerts: phase2ApiMock.listAlerts,
}));

describe('AlertsPage', () => {
  beforeEach(() => {
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    phase2ApiMock.listAlerts.mockResolvedValue([]);
  });

  it('shows the updated empty state message', async () => {
    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(
      screen.getByText('Set up your first alert rule to monitor metric thresholds.'),
    ).toBeInTheDocument();
  });

  it('shows the create action for non-viewer users', async () => {
    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /create alert rule/i })).toBeInTheDocument();
  });

  it('hides the create action for viewer-only users', async () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /create alert rule/i })).not.toBeInTheDocument();
  });
});
