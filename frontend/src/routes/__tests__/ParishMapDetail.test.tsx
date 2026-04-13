import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

import ParishMapDetail from '../ParishMapDetail';
import type { CampaignPerformanceResponse } from '../../state/useDashboardStore';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('../../components/ParishMap', () => ({
  __esModule: true,
  default: () => <div data-testid="parish-map-mock" />,
}));

vi.mock('recharts', () => {
  const MockContainer = ({ children }: { children?: ReactNode }) => (
    <div data-testid="recharts-mock">{children}</div>
  );
  const Passthrough = ({ children }: { children?: ReactNode }) => (
    <svg data-testid="recharts-node">{children}</svg>
  );
  const NullComponent = () => null;
  return {
    ResponsiveContainer: MockContainer,
    BarChart: Passthrough,
    CartesianGrid: NullComponent,
    Tooltip: NullComponent,
    XAxis: NullComponent,
    YAxis: NullComponent,
    Bar: NullComponent,
    Cell: NullComponent,
  };
});

vi.mock('../../auth/AuthContext', () => ({
  __esModule: true,
  useAuth: () => ({ tenantId: 'test-tenant' }),
}));

const campaignData: CampaignPerformanceResponse = {
  summary: {
    currency: 'USD',
    totalSpend: 5000,
    totalImpressions: 200000,
    totalClicks: 1000,
    totalConversions: 100,
    averageRoas: 2.0,
  },
  trend: [],
  rows: [],
};

const parishRows = [
  {
    parish: 'Kingston',
    spend: 540,
    impressions: 120000,
    clicks: 3400,
    conversions: 120,
    roas: 3.5,
    campaignCount: 1,
    currency: 'USD',
  },
  {
    parish: 'Saint Andrew',
    spend: 430,
    impressions: 94000,
    clicks: 4200,
    conversions: 140,
    roas: 4.1,
    campaignCount: 1,
    currency: 'USD',
  },
];

const mockState = {
  filters: {
    dateRange: '7d' as const,
    customRange: { start: '2024-10-01', end: '2024-10-07' },
    accountId: '',
    channels: [],
    campaignQuery: '',
  },
  selectedParish: undefined,
  selectedMetric: 'spend' as const,
  campaign: { status: 'loaded', data: campaignData, error: undefined },
  creative: { status: 'loaded', data: [], error: undefined },
  budget: { status: 'loaded', data: [], error: undefined },
  parish: { status: 'loaded', data: parishRows, error: undefined },
  availability: {
    campaign: { status: 'available' as const, reason: null },
    creative: { status: 'available' as const, reason: null },
    budget: { status: 'available' as const, reason: null },
    parish_map: { status: 'available' as const, reason: null, coveragePercent: 1 },
  },
  activeTenantId: 'demo',
  activeTenantLabel: 'Demo Tenant',
  lastLoadedTenantId: 'demo',
  lastLoadedFiltersKey: undefined,
  metricsCache: {},
  loadAll: vi.fn(),
  setFilters: vi.fn(),
  getCampaignRowsForSelectedParish: () => campaignData.rows,
  getCreativeRowsForSelectedParish: () => [],
  getBudgetRowsForSelectedParish: () => [],
  reset: () => {},
  setSelectedParish: vi.fn(),
  setSelectedMetric: () => {},
  setActiveTenant: () => {},
  getSavedTableView: () => undefined,
  setSavedTableView: () => {},
  clearSavedTableView: () => {},
};

vi.mock('../../state/useDashboardStore', async () => {
  const actual = (await vi.importActual(
    '../../state/useDashboardStore',
  )) as typeof import('../../state/useDashboardStore');

  const useMockDashboardStore = <T,>(
    selector?: (state: typeof mockState) => T,
  ): T | typeof mockState => (selector ? selector(mockState) : mockState);

  Object.assign(useMockDashboardStore, {
    getState: () => mockState,
    setState: (
      updater: Partial<typeof mockState> | ((state: typeof mockState) => Partial<typeof mockState>),
    ) => {
      const next = typeof updater === 'function' ? updater(mockState) : updater;
      Object.assign(mockState, next);
    },
    subscribe: () => () => {},
  });

  return {
    __esModule: true,
    ...actual,
    default: useMockDashboardStore as typeof actual.default,
  };
});

describe('ParishMapDetail', () => {
  it('renders the page header with back button', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: /back to dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: /regional performance/i })).toBeInTheDocument();
  });

  it('renders the map mock', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('parish-map-mock')).toBeInTheDocument();
  });

  it('renders KPI cards with island totals', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    const kpiRow = screen.getByRole('group', { name: /all jamaica kpis/i });
    expect(kpiRow).toBeInTheDocument();
    // KPI labels appear within the metric cards
    expect(kpiRow.querySelectorAll('.metric-card').length).toBe(5);
  });

  it('renders the detail panel empty state when no parish selected', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByText(/no parish selected/i)).toBeInTheDocument();
  });

  it('renders the parish comparison chart card', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /parish comparison/i })).toBeInTheDocument();
  });

  it('renders the region breakdown table card', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <ParishMapDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /region breakdown/i })).toBeInTheDocument();
  });
});
