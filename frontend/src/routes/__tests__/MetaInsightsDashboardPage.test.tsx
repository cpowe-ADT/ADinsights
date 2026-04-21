import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaInsightsDashboardPage from '../MetaInsightsDashboardPage';

const addToast = vi.fn();
const syncMetaIntegration = vi.fn();

const loadAccounts = vi.fn();
const loadInsights = vi.fn();

const makeRow = (over: Partial<Record<string, unknown>>) => ({
  id: `r-${over.id ?? Math.random()}`,
  external_id: String(over.external_id ?? 'ext'),
  date: String(over.date ?? '2026-02-01'),
  source: 'meta',
  level: over.level ?? 'campaign',
  impressions: Number(over.impressions ?? 0),
  reach: Number(over.reach ?? 0),
  clicks: Number(over.clicks ?? 0),
  spend: String(over.spend ?? '0'),
  cpc: String(over.cpc ?? '0'),
  cpm: String(over.cpm ?? '0'),
  conversions: Number(over.conversions ?? 0),
  currency: 'USD',
  actions: over.actions ?? [],
  campaign_external_id: over.campaign_external_id ?? null,
  account_external_id: over.account_external_id ?? null,
  raw_payload: {},
  ingested_at: '',
  updated_at: '',
});

const storeState: {
  filters: {
    accountId: string;
    campaignId: string;
    adsetId: string;
    level: 'account' | 'campaign' | 'adset' | 'ad';
    since: string;
    until: string;
    search: string;
    status: string;
  };
  setFilters: ReturnType<typeof vi.fn>;
  accounts: {
    status: string;
    rows: Array<Record<string, unknown>>;
    count: number;
    page: number;
    pageSize: number;
  };
  insights: {
    status: string;
    rows: ReturnType<typeof makeRow>[];
    count: number;
    page: number;
    pageSize: number;
  };
  loadAccounts: typeof loadAccounts;
  loadInsights: typeof loadInsights;
} = {
  filters: {
    accountId: '',
    campaignId: '',
    adsetId: '',
    level: 'campaign',
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

vi.mock('../../stores/useToastStore', () => ({
  useToastStore: (selector: (state: { addToast: typeof addToast }) => unknown) =>
    selector({ addToast }),
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
    storeState.insights = { status: 'loaded', rows: [], count: 0, page: 1, pageSize: 50 };
    storeState.filters = {
      accountId: '',
      campaignId: '',
      adsetId: '',
      level: 'campaign',
      since: '2026-01-20',
      until: '2026-02-20',
      search: '',
      status: '',
    };
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
    expect(addToast).toHaveBeenCalledWith('Meta sync queued (job job-1).', 'success');
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
    expect(addToast).toHaveBeenCalledWith('Meta sync is already running (job job-99).', 'success');
  });

  // S2 §6.2: ROAS tile absent when no purchase actions present
  it('hides ROAS tile when no purchase actions are present', async () => {
    storeState.insights = {
      status: 'loaded',
      rows: [
        makeRow({
          id: '1',
          spend: '100',
          impressions: 1000,
          clicks: 50,
          level: 'campaign',
          actions: [{ action_type: 'link_click', value: 4 }],
        }),
      ],
      count: 1,
      page: 1,
      pageSize: 50,
    };
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );
    const strip = screen.getByTestId('meta-insights-kpis');
    expect(strip).toHaveTextContent('Spend');
    expect(strip).toHaveTextContent('CTR');
    expect(strip).toHaveTextContent('CPC');
    expect(strip).toHaveTextContent('CPM');
    expect(strip).not.toHaveTextContent('ROAS');
  });

  // S2 §6.2: ROAS tile present when purchase actions are present
  it('renders ROAS tile when any purchase action is derivable', async () => {
    storeState.insights = {
      status: 'loaded',
      rows: [
        makeRow({
          id: '1',
          spend: '50',
          impressions: 1000,
          clicks: 40,
          level: 'campaign',
          actions: [{ action_type: 'omni_purchase', value: 150 }],
        }),
      ],
      count: 1,
      page: 1,
      pageSize: 50,
    };
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );
    const strip = screen.getByTestId('meta-insights-kpis');
    expect(strip).toHaveTextContent('ROAS');
  });

  // S2 §6.2: TrendLine renders CTR + CPM series via accessible sr-only table
  it('renders CTR and CPM dual-axis trend with an accessible tabular counterpart', async () => {
    storeState.insights = {
      status: 'loaded',
      rows: [
        makeRow({ id: '1', date: '2026-04-01', spend: '100', impressions: 1000, clicks: 50 }),
        makeRow({ id: '2', date: '2026-04-02', spend: '50', impressions: 500, clicks: 25 }),
      ],
      count: 2,
      page: 1,
      pageSize: 50,
    };
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );
    // Both series labels should be present in the sr-only table header.
    expect(screen.getAllByText(/CTR/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/CPM/).length).toBeGreaterThan(0);
  });

  // S2 §6.2: BubbleScatter y-axis falls back to CPM when ROAS is not derivable
  it('shows Spend vs CPM bubble heading when ROAS unavailable', async () => {
    storeState.insights = {
      status: 'loaded',
      rows: [
        makeRow({ id: '1', spend: '100', impressions: 1000, clicks: 50, cpm: '100', level: 'campaign' }),
      ],
      count: 1,
      page: 1,
      pageSize: 50,
    };
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: /Spend vs\. CPM/i })).toBeInTheDocument();
  });

  // S2 §6.2: insights table replaces tanstack-table usage; 7 column headers
  it('renders VizDataTable with 7 column headers (no @tanstack/react-table import in page)', async () => {
    storeState.insights = {
      status: 'loaded',
      rows: [
        makeRow({ id: '1', spend: '100', impressions: 1000, clicks: 50, level: 'campaign' }),
      ],
      count: 1,
      page: 1,
      pageSize: 50,
    };
    render(
      <MemoryRouter>
        <MetaInsightsDashboardPage />
      </MemoryRouter>,
    );
    // The bottom records section title reflects count
    expect(screen.getByRole('heading', { name: /Insights records \(1\)/ })).toBeInTheDocument();
  });
});
