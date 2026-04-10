import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDetailPage from '../AlertDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage(alertId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/alerts/${alertId}`]}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
        <Route path="/alerts" element={<div>Alerts list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders alert detail with name, metric, condition, and severity', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({
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
    });

    renderPage();

    expect(await screen.findByText('High CPA alert')).toBeInTheDocument();
    expect(screen.getByText('cost_per_acquisition')).toBeInTheDocument();
    expect(screen.getByText('>')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('24 hours')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to alerts' })).toHaveAttribute(
      'href',
      '/alerts',
    );
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getAlert.mockRejectedValue(new Error('Not found'));

    renderPage();

    expect(await screen.findByText('Alert unavailable')).toBeInTheDocument();
    expect(screen.getByText('Not found')).toBeInTheDocument();
  });

  it('retry reloads alert detail', async () => {
    phase2ApiMock.getAlert.mockRejectedValueOnce(new Error('fail'));

    renderPage();

    await screen.findByText('Alert unavailable');

    phase2ApiMock.getAlert.mockResolvedValue({
      id: 'a1',
      name: 'Recovered alert',
      metric: 'ctr',
      comparison_operator: '<',
      threshold: '1',
      lookback_hours: 12,
      severity: 'warning',
      is_active: true,
      created_at: '2026-04-01T10:00:00Z',
      updated_at: '2026-04-01T10:00:00Z',
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Recovered alert')).toBeInTheDocument();
  });

  it('passes alertId to getAlert', async () => {
    phase2ApiMock.getAlert.mockResolvedValue({
      id: 'a99',
      name: 'Test alert',
      metric: 'spend',
      comparison_operator: '>',
      threshold: '100',
      lookback_hours: 6,
      severity: 'info',
      is_active: true,
      created_at: '2026-04-01T10:00:00Z',
      updated_at: '2026-04-01T10:00:00Z',
    });

    renderPage('a99');

    await screen.findByText('Test alert');
    expect(phase2ApiMock.getAlert).toHaveBeenCalledWith('a99');
  });
});
