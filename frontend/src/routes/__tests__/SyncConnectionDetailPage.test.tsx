import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncConnectionDetailPage from '../SyncConnectionDetailPage';

const phase2ApiMock = vi.hoisted(() => ({
  fetchSyncHealth: vi.fn(),
}));

const airbyteMock = vi.hoisted(() => ({
  triggerAirbyteSync: vi.fn(),
}));

const toastMock = vi.hoisted(() => ({
  pushToast: vi.fn(),
}));

vi.mock('../../lib/phase2Api', () => ({
  fetchSyncHealth: phase2ApiMock.fetchSyncHealth,
}));

vi.mock('../../lib/airbyte', () => ({
  triggerAirbyteSync: airbyteMock.triggerAirbyteSync,
}));

vi.mock('../../stores/useToastStore', () => ({
  default: (selector: (s: { pushToast: typeof toastMock.pushToast }) => unknown) =>
    selector({ pushToast: toastMock.pushToast }),
}));

const sampleRow = {
  id: 'conn-123',
  name: 'Meta Ads Sync',
  provider: 'meta',
  schedule_type: 'manual',
  is_active: true,
  state: 'fresh' as const,
  last_synced_at: '2026-04-10T12:00:00Z',
  last_job_status: 'succeeded',
  last_job_error: null,
};

const sampleResponse = {
  generated_at: '2026-04-10T12:05:00Z',
  stale_after_minutes: 60,
  counts: { total: 1, fresh: 1, stale: 0, failed: 0, missing: 0, inactive: 0 },
  rows: [sampleRow],
};

function renderWithRoute(connectionId: string) {
  return render(
    <MemoryRouter initialEntries={[`/ops/sync-health/${connectionId}`]}>
      <Routes>
        <Route path="/ops/sync-health/:connectionId" element={<SyncConnectionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SyncConnectionDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    phase2ApiMock.fetchSyncHealth.mockResolvedValue(sampleResponse);
    airbyteMock.triggerAirbyteSync.mockResolvedValue({ job_id: 'job-1' });
  });

  it('renders connection details after loading', async () => {
    renderWithRoute('conn-123');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Meta Ads Sync' })).toBeInTheDocument();
    });

    expect(screen.getByText('meta')).toBeInTheDocument();
    expect(screen.getByText('manual')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('fresh')).toBeInTheDocument();
    expect(screen.getByText('succeeded')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument();
  });

  it('shows not found when connection does not exist', async () => {
    renderWithRoute('does-not-exist');

    await waitFor(() => {
      expect(screen.getByText('Connection not found')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/No sync connection found with ID "does-not-exist"/),
    ).toBeInTheDocument();
  });

  it('re-sync button triggers confirm and API call', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithRoute('conn-123');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Meta Ads Sync' })).toBeInTheDocument();
    });

    const resyncButton = screen.getByRole('button', { name: /re-sync/i });
    await user.click(resyncButton);

    expect(confirmSpy).toHaveBeenCalledWith(
      'Are you sure you want to trigger a re-sync for this connection?',
    );
    await waitFor(() => {
      expect(airbyteMock.triggerAirbyteSync).toHaveBeenCalledWith('conn-123');
    });
    expect(toastMock.pushToast).toHaveBeenCalledWith('Re-sync triggered successfully.', {
      tone: 'success',
    });

    confirmSpy.mockRestore();
  });

  it('back link exists and points to sync health', async () => {
    renderWithRoute('conn-123');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Meta Ads Sync' })).toBeInTheDocument();
    });

    const backLink = screen.getByRole('link', { name: /back to sync health/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute('href', '/ops/sync-health');
  });
});
