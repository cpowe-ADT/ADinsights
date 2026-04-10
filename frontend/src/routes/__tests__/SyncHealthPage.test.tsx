import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncHealthPage from '../SyncHealthPage';
import type { SyncHealthResponse } from '../../lib/phase2Api';

const phase2ApiMock = vi.hoisted(() => ({
  fetchSyncHealth: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: phase2ApiMock.fetchSyncHealth,
}));

const sampleResponse: SyncHealthResponse = {
  generated_at: '2026-04-08T12:00:00Z',
  stale_after_minutes: 60,
  counts: {
    total: 5,
    fresh: 2,
    stale: 2,
    failed: 1,
    missing: 0,
    inactive: 0,
  },
  rows: [
    {
      id: 'conn-1',
      name: 'Meta Ads Sync',
      provider: 'Meta',
      schedule_type: 'cron',
      is_active: true,
      state: 'fresh',
      last_synced_at: '2026-04-08T11:50:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: 'conn-2',
      name: 'Google Ads Sync',
      provider: 'Google',
      schedule_type: 'cron',
      is_active: true,
      state: 'stale',
      last_synced_at: '2026-04-07T08:00:00Z',
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: 'conn-3',
      name: 'LinkedIn Ads Sync',
      provider: 'LinkedIn',
      schedule_type: 'manual',
      is_active: true,
      state: 'failed',
      last_synced_at: '2026-04-06T10:00:00Z',
      last_job_status: 'failed',
      last_job_error: 'Connection timeout',
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <SyncHealthPage />
    </MemoryRouter>,
  );
}

describe('SyncHealthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.fetchSyncHealth.mockResolvedValue(sampleResponse);
  });

  it('renders state filter bar with counts', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    expect(await screen.findByText('5')).toBeInTheDocument();

    const statValues = document.querySelectorAll('.phase2-stat__value');
    const values = Array.from(statValues).map((el) => el.textContent);
    expect(values).toEqual(['5', '2', '2', '1']);

    expect(screen.getByText('Total connections')).toBeInTheDocument();
    expect(screen.getByText('Fresh')).toBeInTheDocument();
    expect(screen.getByText('Stale')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders rows in table with correct data', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    expect(await screen.findByText('Meta Ads Sync')).toBeInTheDocument();
    expect(screen.getByText('Google Ads Sync')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn Ads Sync')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Meta' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Google' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'LinkedIn' })).toBeInTheDocument();
  });

  it('renders state pills with correct classes', async () => {
    renderPage();

    const freshPill = await screen.findByText('fresh');
    expect(freshPill).toHaveClass('phase2-pill--fresh');

    const stalePill = screen.getByText('stale');
    expect(stalePill).toHaveClass('phase2-pill--stale');

    const pills = document.querySelectorAll('.phase2-pill--failed');
    expect(pills.length).toBeGreaterThanOrEqual(1);
  });

  it('shows last refreshed timestamp', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    await waitFor(() => {
      const noteElement = document.querySelector('.phase2-note');
      expect(noteElement).not.toBeNull();
      expect(noteElement!.textContent).toContain('Updated');
    });
  });

  it('shows empty state when no sync connections exist', async () => {
    phase2ApiMock.fetchSyncHealth.mockResolvedValue({
      ...sampleResponse,
      counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 },
      rows: [],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('No sync connections')).toBeInTheDocument());
  });

  it('shows error state when API fails', async () => {
    phase2ApiMock.fetchSyncHealth.mockRejectedValue(new Error('Server error'));

    renderPage();

    await waitFor(() => expect(screen.getByText('Sync health unavailable')).toBeInTheDocument());
    expect(screen.getByText('Server error')).toBeInTheDocument();
  });

  it('displays job error messages when present', async () => {
    renderPage();

    await waitFor(() => expect(phase2ApiMock.fetchSyncHealth).toHaveBeenCalled());

    expect(await screen.findByText('Connection timeout')).toBeInTheDocument();
  });
});
