import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertsPage from '../AlertsPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAlerts: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAlerts: phase2ApiMock.listAlerts,
}));

describe('AlertsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders alert rules table when data is available', async () => {
    phase2ApiMock.listAlerts.mockResolvedValue([
      {
        id: 'alert-1',
        name: 'High CPA alert',
        metric: 'cpa',
        comparison_operator: '>',
        threshold: '50',
        lookback_hours: 24,
        severity: 'warning',
        is_active: true,
        created_at: '2026-04-01T12:00:00Z',
        updated_at: '2026-04-01T12:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Alert Rules' })).toBeInTheDocument();
    expect(screen.getByText('High CPA alert')).toBeInTheDocument();
    expect(screen.getByText('cpa')).toBeInTheDocument();
    expect(screen.getByText('warning')).toBeInTheDocument();
  });

  it('shows empty state when no alerts exist', async () => {
    phase2ApiMock.listAlerts.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(screen.getByText('No alert rules')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.listAlerts.mockRejectedValue(new Error('Network error'));

    render(
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.listAlerts).toHaveBeenCalled());
    expect(screen.getByText('Alerts unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });
});
