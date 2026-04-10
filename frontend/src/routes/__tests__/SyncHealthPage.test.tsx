import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncHealthPage from '../SyncHealthPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchSyncHealth: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: phase2ApiMock.fetchSyncHealth,
}));

const mockPayload = {
  generated_at: '2026-04-10T12:00:00Z',
  stale_after_minutes: 60,
  counts: { total: 4, fresh: 2, stale: 1, failed: 1, missing: 0, inactive: 0 },
  rows: [
    {
      id: '1',
      name: 'Meta Ads',
      provider: 'meta',
      schedule_type: 'scheduled',
      is_active: true,
      state: 'fresh',
      last_synced_at: '2026-04-10T11:30:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: '2',
      name: 'Meta Pages',
      provider: 'meta',
      schedule_type: 'scheduled',
      is_active: true,
      state: 'fresh',
      last_synced_at: '2026-04-10T11:35:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: '3',
      name: 'Google Ads',
      provider: 'google',
      schedule_type: 'scheduled',
      is_active: true,
      state: 'stale',
      last_synced_at: '2026-04-09T06:00:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: '4',
      name: 'TikTok Ads',
      provider: 'tiktok',
      schedule_type: 'manual',
      is_active: true,
      state: 'failed',
      last_synced_at: null,
      last_job_status: 'failed',
      last_job_error: 'Connection timeout',
    },
  ],
};

describe('SyncHealthPage', () => {
  beforeEach(() => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue(mockPayload);
  });

  it('renders status filter buttons with counts', async () => {
    render(
      <MemoryRouter>
        <SyncHealthPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: /All \(4\)/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Fresh \(2\)/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Stale \(1\)/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Failed \(1\)/i })).toBeInTheDocument();
  });

  it('filters rows when status filter clicked', async () => {
    render(
      <MemoryRouter>
        <SyncHealthPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    // Initially all 4 rows visible
    expect(screen.getAllByRole('row')).toHaveLength(5); // 4 data rows + 1 header

    // Click Stale filter
    fireEvent.click(screen.getByRole('button', { name: /Stale \(1\)/i }));

    // Only 1 data row + 1 header
    expect(screen.getAllByRole('row')).toHaveLength(2);
    expect(screen.getByText('Google Ads')).toBeInTheDocument();
    expect(screen.queryByText('Meta Ads')).not.toBeInTheDocument();
  });
});
