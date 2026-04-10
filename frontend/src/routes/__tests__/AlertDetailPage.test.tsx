import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDetailPage from '../AlertDetailPage';
import type { AlertRule } from '../../lib/phase2Api';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
}));

const sampleAlert: AlertRule = {
  id: '1',
  name: 'High CPC Alert',
  metric: 'cpc',
  comparison_operator: '>',
  threshold: '5.00',
  lookback_hours: 24,
  severity: 'warning',
  is_active: true,
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-05T14:30:00Z',
};

function renderPage(alertId = '1') {
  return render(
    <MemoryRouter initialEntries={[`/alerts/${alertId}`]}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.getAlert.mockResolvedValue(sampleAlert);
  });

  it('renders alert rule details after loading', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalledWith('1'));
    expect(await screen.findByRole('heading', { name: 'High CPC Alert' })).toBeInTheDocument();
    expect(screen.getByText('cpc')).toBeInTheDocument();
    expect(screen.getByText('>')).toBeInTheDocument();
    expect(screen.getByText('5.00')).toBeInTheDocument();
    expect(screen.getByText('24 hours')).toBeInTheDocument();
    expect(screen.getByText('warning')).toBeInTheDocument();
  });

  it('renders severity pill with correct class', async () => {
    renderPage();

    const pill = await screen.findByText('warning');
    expect(pill).toHaveClass('phase2-pill--warning');
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.getAlert.mockRejectedValue(new Error('Network error'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Alert unavailable')).toBeInTheDocument());
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('refreshes alert data when Refresh button is clicked', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const updatedAlert = { ...sampleAlert, name: 'Updated Alert' };
    phase2ApiMock.getAlert.mockResolvedValue(updatedAlert);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => expect(phase2ApiMock.getAlert).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('heading', { name: 'Updated Alert' })).toBeInTheDocument();
  });

  it('renders back to alerts link', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'High CPC Alert' });

    const backLink = screen.getByRole('link', { name: /back to alerts/i });
    expect(backLink).toHaveAttribute('href', '/alerts');
  });
});
