import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDetailPage from '../AlertDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  getAlert: vi.fn(),
  updateAlert: vi.fn(),
  listNotificationChannels: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  getAlert: phase2ApiMock.getAlert,
  updateAlert: phase2ApiMock.updateAlert,
  listNotificationChannels: phase2ApiMock.listNotificationChannels,
}));

vi.mock('../../lib/format', () => ({
  formatAbsoluteTime: (v: string) => v,
  formatRelativeTime: (v: string) => v,
}));

const sampleAlert = {
  id: 'alert-1',
  name: 'High Spend',
  metric: 'spend',
  comparison_operator: 'gt',
  threshold: '1000',
  lookback_hours: 24,
  severity: 'high',
  is_active: true,
  notification_channels: ['ch-1'],
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

const sampleChannel = {
  id: 'ch-1',
  name: 'Team Slack',
  channel_type: 'slack' as const,
  config: { url: 'https://hooks.slack.com/xxx' },
  is_active: true,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

function renderWithRoute() {
  return render(
    <MemoryRouter initialEntries={['/alerts/alert-1']}>
      <Routes>
        <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AlertDetailPage', () => {
  beforeEach(() => {
    phase2ApiMock.getAlert.mockResolvedValue(sampleAlert);
    phase2ApiMock.listNotificationChannels.mockResolvedValue([sampleChannel]);
    phase2ApiMock.updateAlert.mockResolvedValue(sampleAlert);
  });

  it('renders alert details', async () => {
    renderWithRoute();

    await waitFor(() => expect(screen.getByText('High Spend')).toBeInTheDocument());
    expect(screen.getByText('spend')).toBeInTheDocument();
  });

  it('renders notification channels section', async () => {
    renderWithRoute();

    await waitFor(() =>
      expect(screen.getByText('Notification Channels')).toBeInTheDocument(),
    );
    expect(screen.getByText(/Team Slack/)).toBeInTheDocument();
  });

  it('shows channel checkboxes with correct checked state', async () => {
    renderWithRoute();

    await waitFor(() => expect(screen.getByText(/Team Slack/)).toBeInTheDocument());
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeChecked();
  });

  it('shows error state on load failure', async () => {
    phase2ApiMock.getAlert.mockRejectedValue(new Error('Not found'));

    renderWithRoute();

    await waitFor(() => expect(screen.getByText(/not found/i)).toBeInTheDocument());
  });
});
