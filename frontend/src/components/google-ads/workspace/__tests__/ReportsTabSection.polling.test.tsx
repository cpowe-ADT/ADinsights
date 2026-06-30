import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ReportsTabSection from '../tab-sections/ReportsTabSection';
import type { GoogleAdsExportJob } from '../../../../lib/googleAdsDashboard';

const googleAdsDashboardMock = vi.hoisted(() => ({
  createGoogleAdsExport: vi.fn(),
  fetchGoogleAdsExportStatus: vi.fn(),
  fetchGoogleAdsSavedViews: vi.fn(),
  createGoogleAdsSavedView: vi.fn(),
}));

vi.mock('../../../../lib/googleAdsDashboard', async () => {
  const actual = await vi.importActual<typeof import('../../../../lib/googleAdsDashboard')>(
    '../../../../lib/googleAdsDashboard',
  );
  return {
    ...actual,
    createGoogleAdsExport: googleAdsDashboardMock.createGoogleAdsExport,
    fetchGoogleAdsExportStatus: googleAdsDashboardMock.fetchGoogleAdsExportStatus,
    fetchGoogleAdsSavedViews: googleAdsDashboardMock.fetchGoogleAdsSavedViews,
    createGoogleAdsSavedView: googleAdsDashboardMock.createGoogleAdsSavedView,
  };
});

const runningJob = (): GoogleAdsExportJob => ({
  id: 'job-1',
  name: 'Test export',
  export_format: 'csv',
  status: 'running',
  artifact_path: '',
  error_message: '',
  metadata: {},
  completed_at: null,
  created_at: '2026-04-23T00:00:00Z',
  updated_at: '2026-04-23T00:00:00Z',
});

const completedJob = (): GoogleAdsExportJob => ({
  ...runningJob(),
  status: 'completed',
  completed_at: '2026-04-23T00:00:30Z',
});

/**
 * Drain any pending micro/macro tasks under fake timers. Returning a
 * resolved promise lets queued `.then()` continuations run; calling it a
 * couple of times catches chained awaits inside the polling loop.
 */
async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await flush();
}

describe('ReportsTabSection — GA-A3 polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    googleAdsDashboardMock.fetchGoogleAdsSavedViews.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls until terminal status (completed)', async () => {
    googleAdsDashboardMock.createGoogleAdsExport.mockResolvedValue(runningJob());
    googleAdsDashboardMock.fetchGoogleAdsExportStatus
      .mockResolvedValueOnce(runningJob())
      .mockResolvedValueOnce(completedJob());

    render(<ReportsTabSection initialSavedViews={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create CSV Export' }));
    await flush();

    // First poll fires at 3s.
    await advance(3000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(1);

    // Second poll fires at 6s total; returns completed.
    await advance(3000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(2);

    expect(screen.getByTestId('google-ads-export-status').textContent).toBe('completed');

    // No further polls after terminal.
    await advance(10000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(2);
  });

  it('stops polling at the 60s ceiling', async () => {
    googleAdsDashboardMock.createGoogleAdsExport.mockResolvedValue(runningJob());
    googleAdsDashboardMock.fetchGoogleAdsExportStatus.mockResolvedValue(runningJob());

    render(<ReportsTabSection initialSavedViews={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create CSV Export' }));
    await flush();

    // Advance just past the 60s ceiling in 3s increments.
    for (let i = 0; i < 25; i += 1) {
      await advance(3000);
    }

    const callsAtCeiling = googleAdsDashboardMock.fetchGoogleAdsExportStatus.mock.calls.length;
    // Up to 20 polls before the ceiling guards the next attempt.
    expect(callsAtCeiling).toBeGreaterThan(0);
    expect(callsAtCeiling).toBeLessThanOrEqual(20);

    // Further timer advancement should NOT produce new polls.
    await advance(30000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(callsAtCeiling);
  });

  it('exp-backoff on 5xx and stops after 3 consecutive failures', async () => {
    googleAdsDashboardMock.createGoogleAdsExport.mockResolvedValue(runningJob());
    const { ApiError } = await import('../../../../lib/apiClient');
    const fiveHundred = () => new ApiError('server error', 500);
    googleAdsDashboardMock.fetchGoogleAdsExportStatus
      .mockRejectedValueOnce(fiveHundred())
      .mockRejectedValueOnce(fiveHundred())
      .mockRejectedValueOnce(fiveHundred());

    render(<ReportsTabSection initialSavedViews={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create CSV Export' }));
    await flush();

    // First attempt at 3s.
    await advance(3000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(1);

    // Backoff to 6s for the second attempt — 5999ms is not enough.
    await advance(5999);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(2);

    // Third attempt at 12s after the second.
    await advance(12000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(3);

    // After 3 consecutive 5xx, polling halts and status flips to failed.
    expect(screen.getByTestId('google-ads-export-status').textContent).toBe('failed');

    // Further timer advancement — no new polls.
    await advance(30000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).toHaveBeenCalledTimes(3);
  });

  it('cleanup on unmount halts polling (no state updates after unmount)', async () => {
    googleAdsDashboardMock.createGoogleAdsExport.mockResolvedValue(runningJob());
    googleAdsDashboardMock.fetchGoogleAdsExportStatus.mockResolvedValue(runningJob());

    const { unmount } = render(<ReportsTabSection initialSavedViews={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create CSV Export' }));
    await flush();

    // Unmount before the first 3s tick.
    unmount();

    await advance(15000);
    // setTimeout chain should have been cleared on unmount — zero polls fired.
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).not.toHaveBeenCalled();
  });

  it('skips polling when create returns a terminal status', async () => {
    googleAdsDashboardMock.createGoogleAdsExport.mockResolvedValue(completedJob());

    render(<ReportsTabSection initialSavedViews={[]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create CSV Export' }));
    await flush();

    await advance(30000);
    expect(googleAdsDashboardMock.fetchGoogleAdsExportStatus).not.toHaveBeenCalled();
    expect(screen.getByTestId('google-ads-export-status').textContent).toBe('completed');
  });
});
