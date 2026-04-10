import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AuthContext, type AuthContextValue } from '../../auth/AuthContext';

vi.mock('../../lib/phase2Api', () => ({
  createAlert: vi.fn(),
  listNotificationChannels: vi.fn(),
}));

import { listNotificationChannels } from '../../lib/phase2Api';
import AlertCreatePage from '../AlertCreatePage';

const mockListNotificationChannels = vi.mocked(listNotificationChannels);

function renderWithProviders(ui: React.ReactElement) {
  const authValue: AuthContextValue = {
    status: 'authenticated',
    isAuthenticated: true,
    accessToken: 'test-token',
    tenantId: 'test-tenant',
    user: { roles: ['ADMIN'] },
    login: vi.fn(),
    logout: vi.fn(),
    setActiveTenant: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={['/alerts/new']}>{ui}</MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe('AlertCreatePage', () => {
  it('renders the create form with required fields', async () => {
    mockListNotificationChannels.mockResolvedValue([]);

    renderWithProviders(<AlertCreatePage />);

    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Metric')).toBeInTheDocument();
    expect(screen.getByLabelText('Operator')).toBeInTheDocument();
    expect(screen.getByLabelText('Threshold')).toBeInTheDocument();
    expect(screen.getByLabelText('Lookback (hours)')).toBeInTheDocument();
    expect(screen.getByLabelText('Severity')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create alert' })).toBeInTheDocument();
  });

  it('loads and displays notification channels', async () => {
    mockListNotificationChannels.mockResolvedValue([
      { id: 'ch-1', name: 'Slack Alerts', channel_type: 'slack', is_active: true },
      { id: 'ch-2', name: 'Email Team', channel_type: 'email', is_active: true },
    ]);

    renderWithProviders(<AlertCreatePage />);

    await waitFor(() => {
      expect(screen.getByText(/Slack Alerts/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Email Team/)).toBeInTheDocument();

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
  });

  it('shows a link to create channels when none exist', async () => {
    mockListNotificationChannels.mockResolvedValue([]);

    renderWithProviders(<AlertCreatePage />);

    await waitFor(() => {
      expect(screen.getByText(/No notification channels configured/)).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: 'Create one' })).toHaveAttribute(
      'href',
      '/settings/notifications',
    );
  });
});
