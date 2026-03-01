import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaInsightsDashboardPage from '../MetaInsightsDashboardPage';

const pushToast = vi.fn();
const syncMetaIntegration = vi.fn();

const loadAccounts = vi.fn();
const loadInsights = vi.fn();

const storeState = {
  filters: {
    accountId: '',
    campaignId: '',
    adsetId: '',
    level: 'account' as const,
    since: '2026-01-20',
    until: '2026-02-20',
    search: '',
    status: '',
  },
  setFilters: vi.fn(),
  accounts: {
    status: 'loaded',
    rows: [{ id: '1', external_id: 'act_123', account_id: '123', name: 'Primary Account' }],
    count: 1,
    page: 1,
    pageSize: 50,
  },
  insights: {
    status: 'loaded',
    rows: [],
    count: 0,
    page: 1,
    pageSize: 50,
  },
  loadAccounts,
  loadInsights,
};

vi.mock('../../components/ToastProvider', () => ({
  useToast: () => ({ pushToast }),
}));

vi.mock('../../lib/airbyte', () => ({
  syncMetaIntegration: (...args: unknown[]) => syncMetaIntegration(...args),
}));

vi.mock('../../state/useMetaStore', () => ({
  default: (selector: (state: typeof storeState) => unknown) => selector(storeState),
}));

describe('MetaInsightsDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadAccounts.mockResolvedValue(undefined);
    loadInsights.mockResolvedValue(undefined);
    syncMetaIntegration.mockResolvedValue({
      provider: 'meta_ads',
      connection_id: 'connection-1',
      job_id: 'job-1',
    });
  });

  it('triggers sync from dashboard controls', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(loadAccounts).toHaveBeenCalled();
      expect(loadInsights).toHaveBeenCalled();
    });
    loadAccounts.mockClear();
    loadInsights.mockClear();

    await user.click(screen.getAllByRole('button', { name: 'Sync now' })[0]);

    await waitFor(() => {
      expect(syncMetaIntegration).toHaveBeenCalledTimes(1);
      expect(loadAccounts).toHaveBeenCalledTimes(1);
      expect(loadInsights).toHaveBeenCalledTimes(1);
    });
    expect(pushToast).toHaveBeenCalledWith('Meta sync queued (job job-1).', { tone: 'success' });
  });

  it('shows running sync message when Airbyte returns conflict reuse', async () => {
    syncMetaIntegration.mockResolvedValue({
      provider: 'meta_ads',
      connection_id: 'connection-1',
      job_id: 'job-99',
      reused_existing_job: true,
      sync_status: 'already_running',
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(loadAccounts).toHaveBeenCalled();
      expect(loadInsights).toHaveBeenCalled();
    });
    loadAccounts.mockClear();
    loadInsights.mockClear();

    await user.click(screen.getAllByRole('button', { name: 'Sync now' })[0]);

    await waitFor(() => {
      expect(syncMetaIntegration).toHaveBeenCalledTimes(1);
      expect(loadAccounts).toHaveBeenCalledTimes(1);
      expect(loadInsights).toHaveBeenCalledTimes(1);
    });
    expect(pushToast).toHaveBeenCalledWith('Meta sync is already running (job job-99).', {
      tone: 'success',
    });
  });
});
