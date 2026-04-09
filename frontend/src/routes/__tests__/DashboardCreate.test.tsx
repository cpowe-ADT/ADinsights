import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardCreate from '../DashboardCreate';

const apiMocks = vi.hoisted(() => ({
  loadMetaAccounts: vi.fn(),
  fetchDashboardMetrics: vi.fn(),
  createDashboardDefinition: vi.fn(),
  loadSocialConnectionStatus: vi.fn(),
}));

const datasetStoreMock = vi.hoisted(() => ({
  state: {
    source: 'warehouse' as string | undefined,
    liveReason: 'ready' as
      | 'adapter_disabled'
      | 'missing_snapshot'
      | 'stale_snapshot'
      | 'default_snapshot'
      | 'ready',
    liveDetail: undefined as string | undefined,
  },
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'admin@example.com', roles: ['ADMIN'] },
    tenantId: 'tenant-1',
  }),
}));

vi.mock('../../lib/rbac', () => ({
  canAccessCreatorUi: () => true,
}));

vi.mock('../../lib/meta', () => ({
  loadMetaAccounts: apiMocks.loadMetaAccounts,
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: apiMocks.loadSocialConnectionStatus,
}));

vi.mock('../../lib/dataService', () => ({
  fetchDashboardMetrics: apiMocks.fetchDashboardMetrics,
}));

vi.mock('../../lib/phase2Api', async () => {
  const actual = await vi.importActual('../../lib/phase2Api');
  return {
    ...actual,
    createDashboardDefinition: apiMocks.createDashboardDefinition,
  };
});

vi.mock('../../state/useDatasetStore', () => ({
  useDatasetStore: (
    selector: (state: {
      source?: string;
      liveReason?: 'adapter_disabled' | 'missing_snapshot' | 'stale_snapshot' | 'default_snapshot' | 'ready';
      liveDetail?: string;
    }) => unknown,
  ) => selector(datasetStoreMock.state),
}));

vi.mock('../../components/FilterBar', () => ({
  default: ({
    state,
    onChange,
  }: {
    state: {
      dateRange: string;
      customRange: { start: string; end: string };
      accountId: string;
      channels: string[];
      campaignQuery: string;
    };
    onChange: (value: {
      dateRange: string;
      customRange: { start: string; end: string };
      accountId: string;
      channels: string[];
      campaignQuery: string;
    }) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onChange({
          ...state,
          accountId: 'act_791712443035541',
          channels: ['Meta Ads'],
        })
      }
    >
      Choose SLB
    </button>
  ),
}));

describe('DashboardCreate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    datasetStoreMock.state = {
      source: 'warehouse',
      liveReason: 'ready',
      liveDetail: undefined,
    };
    apiMocks.loadMetaAccounts.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          external_id: 'act_791712443035541',
          account_id: '791712443035541',
          name: "Students' Loan Bureau (SLB)",
        },
      ],
    });
    apiMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'active',
          reason: {
            code: 'active_direct_sync',
            message: 'Meta direct sync completed successfully with fresh reporting rows.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: '2026-04-04T14:55:00Z',
          actions: ['sync_now', 'view'],
          metadata: { credential_account_id: 'act_791712443035541' },
        },
      ],
    });
    apiMocks.fetchDashboardMetrics.mockResolvedValue({
      campaign: {
        summary: {
          currency: 'USD',
          totalSpend: 100,
          totalReach: 1000,
          totalClicks: 50,
          averageRoas: 2.4,
          ctr: 0.05,
        },
        trend: [],
        rows: [{ id: 'cmp-1' }],
      },
      creative: [{ id: 'cr-1' }],
      budget: [{ id: 'bdg-1' }],
      parish: [],
      coverage: { startDate: '2026-01-01', endDate: '2026-03-30' },
      availability: {
        campaign: { status: 'available', reason: null },
        creative: { status: 'available', reason: null },
        budget: { status: 'available', reason: null },
        parish_map: { status: 'unavailable', reason: 'geo_unavailable' },
      },
      snapshot_generated_at: '2026-03-30T12:00:00Z',
    });
    apiMocks.createDashboardDefinition.mockResolvedValue({
      id: 'dash-1',
      name: 'SLB weekly executive overview',
      description: 'Builder output',
      template_key: 'meta_campaign_performance',
      filters: { accountId: 'act_791712443035541' },
      layout: { routeKind: 'campaigns', widgets: ['kpis'] },
      default_metric: 'spend',
      is_active: true,
      owner_email: 'admin@example.com',
      created_at: '2026-03-30T12:00:00Z',
      updated_at: '2026-03-30T12:00:00Z',
    });
  });

  it('saves a real dashboard definition and navigates to the saved-dashboard route', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
          <Route path="/dashboards/saved/:dashboardId" element={<div>Saved dashboard route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Dashboard name'), {
      target: { value: 'SLB weekly executive overview' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Choose SLB' }));

    fireEvent.click(screen.getByRole('button', { name: 'Save dashboard' }));

    await waitFor(() =>
      expect(apiMocks.createDashboardDefinition).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'SLB weekly executive overview',
          template_key: 'meta_campaign_performance',
          default_metric: 'spend',
          is_active: true,
        }),
      ),
    );
    expect(await screen.findByText('Saved dashboard route')).toBeInTheDocument();
  });

  it('prefers the connected live Meta account over placeholder numeric options when auto-selecting preview', async () => {
    apiMocks.loadMetaAccounts.mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          external_id: 'act_335732240',
          account_id: '335732240',
          name: '335732240',
          business_name: 'Adtelligent',
        },
        {
          external_id: 'act_791712443035541',
          account_id: '791712443035541',
          name: "Students' Loan Bureau (SLB)",
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMocks.fetchDashboardMetrics).toHaveBeenCalledWith(
        expect.objectContaining({
          path: expect.stringContaining('account_id=act_791712443035541'),
        }),
      );
    });
  });

  it('waits for Meta status before defaulting so the credential account wins over the first fallback option', async () => {
    let resolveSocialStatus:
      | ((value: Awaited<ReturnType<typeof apiMocks.loadSocialConnectionStatus>>) => void)
      | undefined;
    const socialStatusPromise = new Promise<
      Awaited<ReturnType<typeof apiMocks.loadSocialConnectionStatus>>
    >((resolve) => {
      resolveSocialStatus = resolve;
    });

    apiMocks.loadMetaAccounts.mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          external_id: 'act_335732240',
          account_id: '335732240',
          name: '335732240',
          business_name: 'Adtelligent',
        },
        {
          external_id: 'act_697812007883214',
          account_id: '697812007883214',
          name: 'JDIC Adtelligent Ad Account',
        },
      ],
    });
    apiMocks.loadSocialConnectionStatus.mockReturnValueOnce(socialStatusPromise);

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(apiMocks.fetchDashboardMetrics).not.toHaveBeenCalled();

    resolveSocialStatus?.({
      generated_at: '2026-04-05T00:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'complete',
          reason: {
            code: 'awaiting_recent_successful_sync',
            message: 'Meta setup is complete and awaiting a recent successful direct sync.',
          },
          last_checked_at: '2026-04-05T00:00:00Z',
          last_synced_at: '2026-04-04T22:24:19Z',
          actions: ['sync_now', 'view'],
          metadata: { credential_account_id: 'act_697812007883214' },
        },
      ],
    });

    await waitFor(() => {
      expect(apiMocks.fetchDashboardMetrics).toHaveBeenCalledWith(
        expect.objectContaining({
          path: expect.stringContaining('account_id=act_697812007883214'),
        }),
      );
    });
  });

  it('shows a clear blocked-state preview message when live reporting is disabled', async () => {
    datasetStoreMock.state = {
      source: undefined,
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('Live reporting is not enabled in this environment.'),
    ).toBeInTheDocument();
    expect(apiMocks.fetchDashboardMetrics).not.toHaveBeenCalled();
  });

  it('uses the tenant-scoped stored live account when it is still available', async () => {
    window.localStorage.setItem(
      'adinsights.live-account-selection',
      JSON.stringify({ 'tenant-1': 'act_456' }),
    );
    apiMocks.loadMetaAccounts.mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          external_id: 'act_123',
          account_id: '123',
          name: 'Primary Account',
        },
        {
          external_id: 'act_456',
          account_id: '456',
          name: 'Stored Account',
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMocks.fetchDashboardMetrics).toHaveBeenCalledWith(
        expect.objectContaining({
          path: expect.stringContaining('account_id=act_456'),
        }),
      );
    });
  });

  it('shows an explicit blocked preview state when no Meta ad accounts are available', async () => {
    apiMocks.loadMetaAccounts.mockResolvedValueOnce({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    apiMocks.loadSocialConnectionStatus.mockResolvedValueOnce({
      generated_at: '2026-04-04T15:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'not_connected',
          reason: {
            code: 'missing_meta_credential',
            message: 'Meta OAuth has not been connected for this tenant.',
          },
          last_checked_at: '2026-04-04T15:00:00Z',
          last_synced_at: null,
          actions: ['connect_oauth'],
          metadata: {},
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('Connect Meta first to load ad accounts for dashboard preview.'),
    ).toBeInTheDocument();
    expect(apiMocks.fetchDashboardMetrics).not.toHaveBeenCalled();
  });

  it('shows the exact live warehouse blocker detail when preview is blocked by a fallback snapshot', async () => {
    datasetStoreMock.state = {
      source: 'warehouse',
      liveReason: 'default_snapshot',
      liveDetail:
        'Live warehouse data is blocked because the aggregate warehouse view `vw_dashboard_aggregate_snapshot` is unavailable in this local database.',
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(
        'Live warehouse data is blocked because the aggregate warehouse view `vw_dashboard_aggregate_snapshot` is unavailable in this local database.',
      ),
    ).toBeInTheDocument();
    expect(apiMocks.fetchDashboardMetrics).not.toHaveBeenCalled();
  });

  it('uses the direct Meta source for preview when warehouse reporting is unavailable', async () => {
    datasetStoreMock.state = {
      source: 'meta_direct',
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/create']}>
        <Routes>
          <Route path="/dashboards/create" element={<DashboardCreate />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiMocks.fetchDashboardMetrics).toHaveBeenCalledWith(
        expect.objectContaining({
          path: expect.stringContaining('source=meta_direct'),
        }),
      );
    });
  });
});
