import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CampaignDashboard from '../CampaignDashboard';
import CreativeDashboard from '../CreativeDashboard';
import BudgetDashboard from '../BudgetDashboard';
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
    <div data-testid="recharts-mock">{children}</div>
  ),
}));

vi.mock('../../components/ParishMap', () => ({
  __esModule: true,
  default: () => <div data-testid="parish-map-mock" />,
}));

const storeMock = vi.hoisted(() => ({
  state: {
    loadAll: vi.fn().mockResolvedValue(undefined),
    filters: {
      dateRange: '90d' as const,
      customRange: { start: '2026-01-01', end: '2026-03-30' },
      accountId: 'act_2278682008940745',
      channels: ['Meta Ads'],
      campaignQuery: '',
    },
    setFilters: vi.fn(),
    selectedMetric: 'spend' as const,
    setSelectedMetric: vi.fn(),
    selectedParish: undefined as string | undefined,
    setSelectedParish: vi.fn(),
    campaign: {
      status: 'loaded' as const,
      data: {
        summary: {
          currency: 'USD',
          totalSpend: 0,
          totalImpressions: 0,
          totalReach: 0,
          totalClicks: 0,
          totalConversions: 0,
          averageRoas: 0,
        },
        trend: [],
        rows: [],
      },
      error: undefined,
      errorKind: undefined,
    },
    creative: {
      status: 'loaded' as const,
      data: [],
      error: undefined,
      errorKind: undefined,
    },
    budget: {
      status: 'loaded' as const,
      data: [],
      error: undefined,
      errorKind: undefined,
    },
    parish: {
      status: 'loaded' as const,
      data: [],
      error: undefined,
      errorKind: undefined,
    },
    activeTenantLabel: 'Default Tenant',
    lastSnapshotGeneratedAt: undefined,
    coverage: { startDate: null, endDate: null },
    availability: {
      campaign: { status: 'empty' as const, reason: 'no_recent_data' },
      creative: { status: 'empty' as const, reason: 'no_recent_data' },
      budget: { status: 'empty' as const, reason: 'no_recent_data' },
      parish_map: {
        status: 'unavailable' as const,
        reason: 'geo_unavailable',
        coveragePercent: 0,
      },
    },
    getCampaignRowsForSelectedParish: () => [],
    getCreativeRowsForSelectedParish: () => [],
    getBudgetRowsForSelectedParish: () => [],
  },
}));

const datasetStoreMock = vi.hoisted(() => ({
  state: {
    mode: 'live' as const,
    source: 'warehouse' as 'warehouse' | 'meta_direct' | null | undefined,
    adapters: ['warehouse'],
    liveReason: 'ready' as
      | 'adapter_disabled'
      | 'missing_snapshot'
      | 'stale_snapshot'
      | 'default_snapshot'
      | 'ready',
    liveDetail: undefined as string | undefined,
  },
}));

vi.mock('../../state/useDashboardStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../state/useDatasetStore', () => ({
  useDatasetStore: (
    selector: (state: {
      mode: 'live' | 'dummy';
      source?: 'warehouse' | 'meta_direct' | null;
      adapters: string[];
      liveReason?: 'adapter_disabled' | 'missing_snapshot' | 'stale_snapshot' | 'default_snapshot' | 'ready';
      liveDetail?: string;
    }) => unknown,
  ) => selector(datasetStoreMock.state),
}));

const authValue: AuthContextValue = {
  status: 'authenticated',
  isAuthenticated: true,
  accessToken: 'test-token',
  tenantId: 'tenant-1',
  user: { email: 'admin@example.com' },
  login: vi.fn(),
  logout: vi.fn(),
  statusMessage: undefined,
};

function renderWithAuth(ui: ReactNode) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={authValue}>{ui}</AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe('Meta dashboard empty states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeMock.state.campaign = {
      status: 'loaded',
      data: {
        summary: {
          currency: 'USD',
          totalSpend: 0,
          totalImpressions: 0,
          totalReach: 0,
          totalClicks: 0,
          totalConversions: 0,
          averageRoas: 0,
        },
        trend: [],
        rows: [],
      },
      error: undefined,
      errorKind: undefined,
    };
    storeMock.state.creative = {
      status: 'loaded',
      data: [],
      error: undefined,
      errorKind: undefined,
    };
    storeMock.state.budget = {
      status: 'loaded',
      data: [],
      error: undefined,
      errorKind: undefined,
    };
    datasetStoreMock.state = {
      mode: 'live',
      adapters: ['warehouse'],
      liveReason: 'ready',
      liveDetail: undefined,
    };
  });

  it('shows a truthful no recent data message on the campaign dashboard', () => {
    renderWithAuth(<CampaignDashboard />);

    expect(screen.getByText('No recent reportable data')).toBeInTheDocument();
    expect(
      screen.getByText(
        'The selected Meta account is connected, but Meta returned no recent reportable campaign results for this window.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a truthful no recent data message on the creative dashboard', () => {
    renderWithAuth(<CreativeDashboard />);

    expect(screen.getByText('No recent reportable data')).toBeInTheDocument();
    expect(
      screen.getByText(
        'The selected Meta account is connected, but Meta returned no recent reportable creative results for this window.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a truthful no recent data message on the budget dashboard', () => {
    renderWithAuth(<BudgetDashboard />);

    expect(screen.getByText('No recent reportable data')).toBeInTheDocument();
    expect(
      screen.getByText(
        'The selected Meta account is connected, but Meta returned no recent reportable budget-backed delivery for this window.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a truthful blocked state on the campaign dashboard when live reporting is disabled', () => {
    storeMock.state.campaign = {
      status: 'error',
      data: undefined,
      error: 'Live reporting is not enabled in this environment.',
      errorKind: 'generic',
    };
    datasetStoreMock.state = {
      mode: 'live',
      source: 'warehouse' as const,
      adapters: [],
      liveReason: 'adapter_disabled',
      liveDetail: undefined,
    };

    renderWithAuth(<CampaignDashboard />);

    expect(screen.getByText('Live reporting disabled')).toBeInTheDocument();
    expect(
      screen.getAllByText('Live reporting is not enabled in this environment.'),
    ).toHaveLength(2);
  });

  it('shows the exact warehouse blocker detail on the budget dashboard', () => {
    storeMock.state.budget = {
      status: 'error',
      data: undefined,
      error:
        'Live warehouse data is blocked because the aggregate warehouse view `vw_dashboard_aggregate_snapshot` is unavailable in this local database.',
      errorKind: 'generic',
    };
    datasetStoreMock.state = {
      mode: 'live',
      source: 'warehouse' as const,
      adapters: ['warehouse'],
      liveReason: 'default_snapshot',
      liveDetail:
        'Live warehouse data is blocked because the aggregate warehouse view `vw_dashboard_aggregate_snapshot` is unavailable in this local database.',
    };

    renderWithAuth(<BudgetDashboard />);

    expect(screen.getByText('Fallback live snapshot')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Live warehouse data is blocked because the aggregate warehouse view `vw_dashboard_aggregate_snapshot` is unavailable in this local database.',
      ),
    ).toBeInTheDocument();
  });
});
