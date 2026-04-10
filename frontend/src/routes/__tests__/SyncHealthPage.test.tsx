import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import type { SyncHealthResponse } from '../../lib/phase2Api';

const MOCK_RESPONSE: SyncHealthResponse = {
  generated_at: new Date().toISOString(),
  stale_after_minutes: 60,
  counts: { total: 3, fresh: 1, stale: 1, failed: 1, missing: 0, inactive: 0 },
  rows: [
    {
      id: 'conn-1',
      name: 'Meta Ads',
      provider: 'meta',
      schedule_type: 'cron',
      is_active: true,
      state: 'fresh',
      last_synced_at: new Date().toISOString(),
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: 'conn-2',
      name: 'Google Ads',
      provider: 'google',
      schedule_type: 'cron',
      is_active: true,
      state: 'stale',
      last_synced_at: new Date(Date.now() - 7200000).toISOString(),
      last_job_status: 'succeeded',
      last_job_error: null,
    },
    {
      id: 'conn-3',
      name: 'LinkedIn Ads',
      provider: 'linkedin',
      schedule_type: 'manual',
      is_active: true,
      state: 'failed',
      last_synced_at: null,
      last_job_status: 'failed',
      last_job_error: 'Timeout',
    },
  ],
};

const mockFetchSyncHealth = vi.fn<() => Promise<SyncHealthResponse>>();
const mockTriggerSync = vi.fn<() => Promise<{ status: string; connection_id: string }>>();

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: (...args: unknown[]) => mockFetchSyncHealth(...(args as [])),
  triggerSync: (...args: unknown[]) => mockTriggerSync(...(args as [])),
}));

// Lazy import so the mock is in place before the module loads
const loadComponent = async () => {
  const mod = await import('../SyncHealthPage');
  return mod.default;
};

describe('SyncHealthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchSyncHealth.mockResolvedValue(structuredClone(MOCK_RESPONSE));
    mockTriggerSync.mockResolvedValue({ status: 'triggered', connection_id: 'conn-1' });
  });

  it('renders state filter buttons', async () => {
    const SyncHealthPage = await loadComponent();
    render(<SyncHealthPage />);

    // Wait for data to load
    const filterGroup = await screen.findByRole('group', { name: /State filter/ });
    expect(filterGroup).toBeInTheDocument();

    const buttons = within(filterGroup).getAllByRole('button');
    const labels = buttons.map((b) => b.textContent);
    expect(labels).toContain('All');
    expect(labels.some((l) => l?.startsWith('Fresh'))).toBe(true);
    expect(labels.some((l) => l?.startsWith('Stale'))).toBe(true);
    expect(labels.some((l) => l?.startsWith('Failed'))).toBe(true);
    expect(labels.some((l) => l?.startsWith('Missing'))).toBe(true);
    expect(labels.some((l) => l?.startsWith('Inactive'))).toBe(true);
  });

  it('filtering by state shows correct rows', async () => {
    const user = userEvent.setup();
    const SyncHealthPage = await loadComponent();
    render(<SyncHealthPage />);

    // Wait for initial load
    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();
    expect(screen.getByText('Google Ads')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn Ads')).toBeInTheDocument();

    // Click Stale filter within the filter toolbar
    const filterGroup = screen.getByRole('group', { name: /State filter/ });
    const staleButton = within(filterGroup).getByRole('button', { name: /Stale/ });
    await user.click(staleButton);

    // Only stale row should be visible
    expect(screen.getByText('Google Ads')).toBeInTheDocument();
    expect(screen.queryByText('Meta Ads')).not.toBeInTheDocument();
    expect(screen.queryByText('LinkedIn Ads')).not.toBeInTheDocument();
  });

  it('trigger re-sync button appears per row', async () => {
    const SyncHealthPage = await loadComponent();
    render(<SyncHealthPage />);

    // Wait for data to load
    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();

    const resyncButtons = screen.getAllByRole('button', { name: 'Re-sync' });
    expect(resyncButtons).toHaveLength(3);
  });

  it('refresh button reloads data', async () => {
    const user = userEvent.setup();
    const SyncHealthPage = await loadComponent();
    render(<SyncHealthPage />);

    // Wait for initial load
    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();
    expect(mockFetchSyncHealth).toHaveBeenCalledTimes(1);

    // Click the Refresh button
    const refreshButton = screen.getByRole('button', { name: 'Refresh' });
    await user.click(refreshButton);

    // fetchSyncHealth should have been called again
    expect(mockFetchSyncHealth).toHaveBeenCalledTimes(2);
  });
});
