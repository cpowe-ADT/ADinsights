import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncHealthPage from '../SyncHealthPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchSyncHealth: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: phase2ApiMock.fetchSyncHealth,
}));

vi.mock('../../lib/format', () => ({
  formatRelativeTime: (v: string) => `rel(${v})`,
  formatAbsoluteTime: (v: string) => `abs(${v})`,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <SyncHealthPage />
    </MemoryRouter>,
  );
}

const healthPayload = {
  generated_at: '2026-04-01T12:00:00Z',
  stale_after_minutes: 60,
  counts: { total: 3, fresh: 2, stale: 1, failed: 0, missing: 0, inactive: 0 },
  rows: [
    {
      id: 'c1',
      name: 'Meta Ads',
      provider: 'airbyte',
      schedule_type: 'cron',
      is_active: true,
      state: 'fresh' as const,
      last_synced_at: '2026-04-01T11:55:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: 'c2',
      name: 'Google Ads',
      provider: 'sdk',
      schedule_type: 'manual',
      is_active: true,
      state: 'stale' as const,
      last_synced_at: '2026-03-30T10:00:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
  ],
};

describe('SyncHealthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders stat cards and connection rows', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue(healthPayload);

    renderPage();

    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();
    expect(screen.getByText('Google Ads')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument(); // total
    expect(screen.getByText('2')).toBeInTheDocument(); // fresh
    expect(screen.getByText('fresh')).toBeInTheDocument();
    expect(screen.getByText('stale')).toBeInTheDocument();
  });

  it('shows empty state when no connections', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      stale_after_minutes: 60,
      counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 },
      rows: [],
    });

    renderPage();

    expect(await screen.findByText('No sync connections')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.fetchSyncHealth.mockRejectedValue(new Error('Timeout'));

    renderPage();

    expect(await screen.findByText('Sync health unavailable')).toBeInTheDocument();
    expect(screen.getByText('Timeout')).toBeInTheDocument();
  });

  it('refresh button reloads data', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      ...healthPayload,
      rows: [],
      counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 },
    });

    renderPage();

    await screen.findByText('No sync connections');

    phase2ApiMock.fetchSyncHealth.mockResolvedValue(healthPayload);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();
  });

  it('displays last job error when present', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      ...healthPayload,
      rows: [
        {
          id: 'c3',
          name: 'Failed connection',
          provider: 'airbyte',
          schedule_type: 'cron',
          is_active: true,
          state: 'failed',
          last_synced_at: null,
          last_job_status: 'failed',
          last_job_error: 'Rate limit exceeded',
        },
      ],
    });

    renderPage();

    expect(await screen.findByText('Failed connection')).toBeInTheDocument();
    expect(screen.getByText('Rate limit exceeded')).toBeInTheDocument();
  });
});
