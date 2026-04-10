import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardLayout from '../DashboardLayout';
import { loadMetaAccounts } from '../../lib/meta';

const storeMock = vi.hoisted(() => ({
  state: {
    loadAll: vi.fn().mockResolvedValue(undefined),
    filters: {
      dateRange: '7d' as const,
      customRange: { start: '2026-02-13', end: '2026-02-19' },
      accountId: '',
      channels: [],
      campaignQuery: '',
    },
    setFilters: vi.fn(),
    selectedMetric: 'spend' as const,
    setSelectedMetric: vi.fn(),
    selectedParish: undefined as string | undefined,
    setSelectedParish: vi.fn(),
    campaign: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
      errorKind: undefined,
    },
    creative: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
      errorKind: undefined,
    },
    budget: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
      errorKind: undefined,
    },
    parish: {
      status: 'error' as const,
      data: undefined,
      error: 'Creative metrics invalid in aggregated response',
      errorKind: undefined,
    },
    activeTenantLabel: 'Default Tenant',
    lastSnapshotGeneratedAt: undefined,
  },
}));

const authMock = vi.hoisted(() => ({
  user: { email: 'admin@example.com', roles: ['ADMIN'] },
}));

const airbyteMock = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn().mockResolvedValue({
    generated_at: '2026-04-05T00:00:00Z',
    platforms: [
      {
        platform: 'meta',
        display_name: 'Meta (Facebook)',
        status: 'active',
        reason: {
          code: 'active_direct_sync',
          message: 'Meta direct sync completed successfully with fresh reporting rows.',
        },
        metadata: { credential_account_id: 'act_697812007883214' },
      },
    ],
  }),
}));

const datasetStoreMock = vi.hoisted(() => ({
  state: {
    mode: 'live' as const,
    adapters: ['warehouse'],
    status: 'loaded' as const,
    source: 'warehouse' as string | undefined,
    liveReason: 'ready' as
      | 'adapter_disabled'
      | 'missing_snapshot'
      | 'stale_snapshot'
      | 'default_snapshot'
      | 'ready',
    liveDetail: undefined as string | undefined,
    liveSnapshotGeneratedAt: undefined as string | undefined,
    warehouseAdapterEnabled: true,
  },
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    tenantId: 'tenant-1',
    logout: vi.fn(),
    user: authMock.user,
  }),
}));

vi.mock('../../components/ThemeProvider', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: vi.fn(),
  }),
}));

vi.mock('../../components/ToastProvider', () => ({
  useToast: () => ({
    pushToast: vi.fn(),
  }),
}));

vi.mock('../../components/Breadcrumbs', () => ({
  default: () => <div data-testid="breadcrumbs" />,
}));

vi.mock('../../components/FilterBar', () => ({
  default: () => <div data-testid="filter-bar" />,
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMock.loadSocialConnectionStatus,
}));

vi.mock('../../lib/meta', () => ({
  loadMetaAccounts: vi.fn().mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  }),
}));

vi.mock('../../components/DatasetToggle', () => ({
  default: () => <div data-testid="dataset-toggle" />,
}));

vi.mock('../../components/TenantSwitcher', () => ({
  default: () => <div data-testid="tenant-switcher" />,
}));

vi.mock('../../components/SnapshotIndicator', () => ({
  default: () => <div data-testid="snapshot-indicator" />,
}));

vi.mock('../../state/useDashboardStore', () => {
  const hook = (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state);
  hook.getState = () => storeMock.state;
  return { default: hook };
});

vi.mock('../../state/useDatasetStore', () => ({
  useDatasetStore: (
    selector: (state: {
      mode: 'live' | 'dummy';
      adapters: string[];
      status: 'idle' | 'loading' | 'loaded' | 'error';
      source?: string;
      liveReason?: 'adapter_disabled' | 'missing_snapshot' | 'stale_snapshot' | 'default_snapshot' | 'ready';
      liveDetail?: string;
      liveSnapshotGeneratedAt?: string;
      warehouseAdapterEnabled: boolean;
    }) => unknown,
  ) => selector(datasetStoreMock.state),
}));

describe('DashboardLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.user = { email: 'admin@example.com', roles: ['ADMIN'] };
    datasetStoreMock.state = {
      mode: 'live',
      adapters: ['warehouse'],
      status: 'loaded',
      source: 'warehouse',
      liveReason: 'ready',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: true,
    };
  });

  it('deduplicates repeated dashboard error messages', () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getAllByText('Creative metrics invalid in aggregated response')).toHaveLength(1);
  });

  it('hides the create nav link for viewer-only users', () => {
    authMock.user = { email: 'viewer@example.com', roles: ['VIEWER'] };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByRole('link', { name: 'Create' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Campaigns' })).toBeInTheDocument();
  });

  it('does not overwrite saved dashboard filters from an empty route query', () => {
    storeMock.state.filters = {
      dateRange: '90d',
      customRange: { start: '2026-01-01', end: '2026-03-30' },
      accountId: 'act_697812007883214',
      channels: ['Meta Ads'],
      campaignQuery: 'Debt Reset',
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/saved/dash-1']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="saved/:dashboardId" element={<div>Saved dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(storeMock.state.setFilters).not.toHaveBeenCalled();
    expect(screen.getByText('Saved dashboard')).toBeInTheDocument();
  });

  it('waits for dataset availability before loading dashboard metrics', () => {
    datasetStoreMock.state = {
      mode: 'live',
      adapters: [],
      status: 'idle',
      source: undefined,
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: false,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(storeMock.state.loadAll).not.toHaveBeenCalled();
  });

  it('loads dashboard metrics once the warehouse dataset is available', async () => {
    datasetStoreMock.state = {
      mode: 'live',
      adapters: ['warehouse'],
      status: 'loaded',
      source: 'warehouse',
      liveReason: 'ready',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: '2026-04-04T10:00:00Z',
      warehouseAdapterEnabled: true,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(storeMock.state.loadAll).toHaveBeenCalledWith('tenant-1');
    });
  });

  it('renders persistent home and connect socials shortcuts in the dashboard shell', () => {
    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Connect socials' })).toHaveAttribute(
      'href',
      '/dashboards/data-sources?sources=social',
    );
  });

  it('renders adapter-disabled live reporting guidance when warehouse access is off', () => {
    datasetStoreMock.state = {
      mode: 'live',
      adapters: [],
      status: 'loaded',
      source: undefined,
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: false,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText('Live reporting is not enabled in this environment.'),
    ).toBeInTheDocument();
  });

  it('renders missing-snapshot guidance when Meta is connected but no live snapshot exists', () => {
    datasetStoreMock.state = {
      mode: 'live',
      adapters: ['warehouse'],
      status: 'loaded',
      source: 'warehouse',
      liveReason: 'missing_snapshot',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: undefined,
      warehouseAdapterEnabled: true,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText(
        'Meta is connected, but the first live warehouse snapshot has not been generated yet.',
      ),
    ).toBeInTheDocument();
  });

  it('renders direct Meta guidance and still loads dashboards when live source is meta_direct', async () => {
    datasetStoreMock.state = {
      mode: 'live',
      adapters: ['meta_direct'],
      status: 'loaded',
      source: 'meta_direct',
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
      liveSnapshotGeneratedAt: '2026-04-04T10:00:00Z',
      warehouseAdapterEnabled: false,
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText(
        'Showing direct Meta sync data. Warehouse reporting is not enabled in this environment.',
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(storeMock.state.loadAll).toHaveBeenCalledWith('tenant-1');
    });
  });

  it('waits for Meta status before auto-selecting the preferred credential account', async () => {
    let resolveStatus:
      | ((value: Awaited<ReturnType<typeof airbyteMock.loadSocialConnectionStatus>>) => void)
      | undefined;
    const deferredStatus = new Promise<
      Awaited<ReturnType<typeof airbyteMock.loadSocialConnectionStatus>>
    >((resolve) => {
      resolveStatus = resolve;
    });

    airbyteMock.loadSocialConnectionStatus.mockReturnValueOnce(deferredStatus);
    vi.mocked(loadMetaAccounts).mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: '1',
          external_id: 'act_335732240',
          account_id: '335732240',
          name: '335732240',
          currency: 'USD',
          status: '1',
          business_name: 'Adtelligent',
          metadata: {},
          created_at: '2026-04-05T00:00:00Z',
          updated_at: '2026-04-05T00:00:00Z',
        },
        {
          id: '2',
          external_id: 'act_697812007883214',
          account_id: '697812007883214',
          name: 'JDIC Adtelligent Ad Account',
          currency: 'USD',
          status: '1',
          business_name: '',
          metadata: {},
          created_at: '2026-04-05T00:00:00Z',
          updated_at: '2026-04-05T00:00:00Z',
        },
      ],
    });
    storeMock.state.filters = {
      dateRange: '7d',
      customRange: { start: '2026-02-13', end: '2026-02-19' },
      accountId: '',
      channels: [],
      campaignQuery: '',
    };

    render(
      <MemoryRouter initialEntries={['/dashboards/campaigns']}>
        <Routes>
          <Route path="/dashboards" element={<DashboardLayout />}>
            <Route path="campaigns" element={<div>Campaigns</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(storeMock.state.setFilters).not.toHaveBeenCalledWith(
      expect.objectContaining({ accountId: 'act_335732240' }),
    );

    resolveStatus?.({
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
          metadata: { credential_account_id: 'act_697812007883214' },
        },
      ],
    });

    await waitFor(() => {
      expect(storeMock.state.setFilters).toHaveBeenCalledWith(
        expect.objectContaining({ accountId: 'act_697812007883214' }),
      );
    });
  });
});
