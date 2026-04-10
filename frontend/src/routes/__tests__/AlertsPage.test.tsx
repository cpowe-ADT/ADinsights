import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertsPage from '../AlertsPage';

const phase2ApiMock = vi.hoisted(() => ({
  listAlerts: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  listAlerts: phase2ApiMock.listAlerts,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );
}

describe('AlertsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders table with alert rule data', async () => {
    phase2ApiMock.listAlerts.mockResolvedValue([
      {
        id: 'a1',
        name: 'High CPA alert',
        metric: 'cost_per_acquisition',
        comparison_operator: '>',
        threshold: '50',
        lookback_hours: 24,
        severity: 'critical',
        is_active: true,
        created_at: '2026-04-01T10:00:00Z',
        updated_at: '2026-04-01T10:00:00Z',
      },
    ]);

    renderPage();

    expect(await screen.findByText('High CPA alert')).toBeInTheDocument();
    expect(screen.getByText('cost_per_acquisition')).toBeInTheDocument();
    expect(screen.getByText('> 50 (24h)')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/alerts/a1');
  });

  it('shows empty state when no alerts', async () => {
    phase2ApiMock.listAlerts.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText('No alert rules')).toBeInTheDocument();
    expect(
      screen.getByText('Create alert rules in admin to drive this view.'),
    ).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.listAlerts.mockRejectedValue(new Error('Server error'));

    renderPage();

    expect(await screen.findByText('Alerts unavailable')).toBeInTheDocument();
    expect(screen.getByText('Server error')).toBeInTheDocument();
  });

  it('refresh button reloads data', async () => {
    phase2ApiMock.listAlerts.mockResolvedValue([]);

    renderPage();

    await screen.findByText('No alert rules');

    phase2ApiMock.listAlerts.mockResolvedValue([
      {
        id: 'a2',
        name: 'Low CTR alert',
        metric: 'ctr',
        comparison_operator: '<',
        threshold: '1',
        lookback_hours: 12,
        severity: 'warning',
        is_active: true,
        created_at: '2026-04-02T10:00:00Z',
        updated_at: '2026-04-02T10:00:00Z',
      },
    ]);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(await screen.findByText('Low CTR alert')).toBeInTheDocument();
  });

  it('retry action reloads after error', async () => {
    phase2ApiMock.listAlerts.mockRejectedValueOnce(new Error('fail'));

    renderPage();

    await screen.findByText('Alerts unavailable');

    phase2ApiMock.listAlerts.mockResolvedValue([]);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('No alert rules')).toBeInTheDocument();
  });
});
