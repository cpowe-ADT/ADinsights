import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncHealthPage from '../SyncHealthPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchSyncHealth: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: phase2ApiMock.fetchSyncHealth,
}));

describe('SyncHealthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders sync health stats and connection rows', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      stale_after_minutes: 120,
      counts: { total: 2, fresh: 1, stale: 1, failed: 0, missing: 0, inactive: 0 },
      rows: [
        {
          id: 'conn-1',
          name: 'Meta Ads sync',
          provider: 'meta',
          schedule_type: 'cron',
          is_active: true,
          state: 'fresh',
          last_synced_at: '2026-04-01T11:00:00Z',
          last_job_status: 'succeeded',
          last_job_error: null,
        },
        {
          id: 'conn-2',
          name: 'Google Ads sync',
          provider: 'google',
          schedule_type: 'cron',
          is_active: true,
          state: 'stale',
          last_synced_at: '2026-03-31T08:00:00Z',
          last_job_status: 'succeeded',
          last_job_error: null,
        },
      ],
    });

    render(
      <MemoryRouter>
        <SyncHealthPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());
    expect(screen.getByRole('heading', { name: 'Sync Health' })).toBeInTheDocument();
    expect(screen.getByText('Meta Ads sync')).toBeInTheDocument();
    expect(screen.getByText('Google Ads sync')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // total connections
  });

  it('shows empty state when no connections exist', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      generated_at: '2026-04-01T12:00:00Z',
      stale_after_minutes: 120,
      counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 },
      rows: [],
    });

    render(
      <MemoryRouter>
        <SyncHealthPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());
    expect(screen.getByText('No sync connections')).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    phase2ApiMock.fetchSyncHealth.mockRejectedValue(new Error('Connection refused'));

    render(
      <MemoryRouter>
        <SyncHealthPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());
    expect(screen.getByText('Sync health unavailable')).toBeInTheDocument();
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });
});
