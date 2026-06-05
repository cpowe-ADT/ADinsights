import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const navigateMock = vi.hoisted(() => vi.fn());

const storeMock = vi.hoisted(() => ({
  state: {
    accounts: {
      status: 'loaded' as const,
      rows: [
        {
          id: 'acct-1',
          name: 'Primary Account',
          external_id: 'act_123',
          account_id: '123',
          currency: 'USD',
          status: 'ACTIVE',
          business_name: 'Demo Biz',
        },
      ],
      count: 1,
      error: '',
      errorCode: '',
    },
    campaigns: {
      status: 'loaded' as const,
      rows: [
        {
          id: 'camp-1',
          external_id: 'cmp_1',
          name: 'Cmp 1',
          platform: 'meta',
          status: 'ACTIVE',
          objective: 'CONVERSIONS',
          currency: 'USD',
          account_external_id: 'act_123',
          metadata: {},
          created_at: '',
          updated_at: '',
        },
        {
          id: 'camp-2',
          external_id: 'cmp_2',
          name: 'Cmp 2',
          platform: 'meta',
          status: 'ACTIVE',
          objective: 'TRAFFIC',
          currency: 'USD',
          account_external_id: 'act_123',
          metadata: {},
          created_at: '',
          updated_at: '',
        },
      ],
      count: 2,
    },
    insights: {
      status: 'loaded' as const,
      rows: [
        {
          id: 'i1',
          external_id: 'ins1',
          date: '2026-04-01',
          source: 'meta',
          level: 'account' as const,
          impressions: 1000,
          reach: 800,
          clicks: 50,
          spend: '100',
          cpc: '2',
          cpm: '100',
          conversions: 5,
          currency: 'USD',
          actions: [],
          campaign_external_id: 'cmp_1',
          account_external_id: 'act_123',
          raw_payload: {},
          ingested_at: '',
          updated_at: '',
        },
        {
          id: 'i2',
          external_id: 'ins2',
          date: '2026-04-01',
          source: 'meta',
          level: 'account' as const,
          impressions: 500,
          reach: 400,
          clicks: 20,
          spend: '50',
          cpc: '2.5',
          cpm: '100',
          conversions: 2,
          currency: 'USD',
          actions: [],
          campaign_external_id: 'cmp_2',
          account_external_id: 'act_456',
          raw_payload: {},
          ingested_at: '',
          updated_at: '',
        },
      ],
      count: 2,
    },
    filters: {
      accountId: '',
      campaignId: '',
      adsetId: '',
      level: 'account',
      search: '',
      status: '',
      since: '',
      until: '',
    },
    setFilters: vi.fn(),
    loadAccounts: vi.fn().mockResolvedValue(undefined),
    loadCampaigns: vi.fn().mockResolvedValue(undefined),
    loadInsights: vi.fn().mockResolvedValue(undefined),
  },
}));

const airbyteMocks = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn(),
  previewMetaRecovery: vi.fn(),
}));

import MetaAccountsPage from '../MetaAccountsPage';

vi.mock('../../state/useMetaStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
  previewMetaRecovery: airbyteMocks.previewMetaRecovery,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe('MetaAccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    storeMock.state.accounts = {
      status: 'loaded' as const,
      rows: [
        {
          id: 'acct-1',
          name: 'Primary Account',
          external_id: 'act_123',
          account_id: '123',
          currency: 'USD',
          status: 'ACTIVE',
          business_name: 'Demo Biz',
        },
      ],
      count: 1,
      error: '',
      errorCode: '',
    };
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [],
    });
  });

  it('explains that Meta accounts and Facebook pages are separate assets', async () => {
    render(
      <MemoryRouter>
        <MetaAccountsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Meta ad accounts and Facebook Pages are separate assets\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Facebook pages' })).toHaveAttribute(
      'href',
      '/dashboards/meta/pages',
    );
  });

  // C1A-NEW-01: clicking a normal (non-recovery) row propagates accountId
  // and navigates to the Insights route for that account.
  it('calls setFilters and navigates on row click', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <MetaAccountsPage />
        </MemoryRouter>,
      );
    });

    const row = screen.getByRole('row', { name: /Select account Primary Account/i });
    fireEvent.click(row);
    expect(storeMock.state.setFilters).toHaveBeenCalledWith({ accountId: 'act_123' });
    expect(navigateMock).toHaveBeenCalledWith('/dashboards/meta/insights?accountId=act_123');
  });

  // C1A-NEW-01: clicking a recovery-fallback row must NOT call setFilters (ghost ID guard)
  it('does not call setFilters when a recovery-fallback row is clicked', async () => {
    storeMock.state.accounts = {
      ...storeMock.state.accounts,
      status: 'loaded' as const,
      rows: [],
      count: 0,
    };
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: { code: 'orphaned_marketing_access', message: 'Restore access.' },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: null,
          actions: ['recover_marketing_access'],
          metadata: { has_recoverable_marketing_access: true },
        },
      ],
    });
    airbyteMocks.previewMetaRecovery.mockResolvedValue({
      ad_accounts: [
        {
          id: 'act_recovery_999',
          name: 'Recovery Account',
          account_id: '999',
          currency: 'USD',
          account_status: 1,
          business_name: 'Biz',
        },
      ],
    });

    await act(async () => {
      render(
        <MemoryRouter>
          <MetaAccountsPage />
        </MemoryRouter>,
      );
    });

    const row = await screen.findByRole('row', { name: /Select account Recovery Account/i });
    fireEvent.click(row);
    expect(storeMock.state.setFilters).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  // S2 §6.1: dispatches loadInsights + loadCampaigns alongside loadAccounts
  it('dispatches loadAccounts, loadCampaigns, and loadInsights on mount', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <MetaAccountsPage />
        </MemoryRouter>,
      );
    });
    expect(storeMock.state.loadAccounts).toHaveBeenCalled();
    expect(storeMock.state.loadCampaigns).toHaveBeenCalled();
    expect(storeMock.state.loadInsights).toHaveBeenCalled();
  });

  // S2 §6.1: KPI strip renders 6 KpiTile labels
  it('renders 6 KPI tile labels (Spend, Impressions, Reach, CTR, CPM, Active accounts)', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <MetaAccountsPage />
        </MemoryRouter>,
      );
    });
    const strip = screen.getByTestId('meta-accounts-kpis');
    expect(strip).toHaveTextContent('Spend');
    expect(strip).toHaveTextContent('Impressions');
    expect(strip).toHaveTextContent('Reach');
    expect(strip).toHaveTextContent('CTR');
    expect(strip).toHaveTextContent('CPM');
    expect(strip).toHaveTextContent('Active accounts');
  });

  // S2 §6.1: PieComposition receives slices from join of insights × campaigns
  it('renders objective pie composition with joined spend slices', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <MetaAccountsPage />
        </MemoryRouter>,
      );
    });
    // PieComposition renders an accessible sr-only table with one row per slice
    // labelled "Spend by campaign objective". Confirm the two objectives are present.
    expect(screen.getAllByText(/CONVERSIONS/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/TRAFFIC/i).length).toBeGreaterThan(0);
  });
});
