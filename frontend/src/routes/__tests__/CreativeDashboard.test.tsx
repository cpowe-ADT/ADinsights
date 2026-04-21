import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CreativeDashboard from '../CreativeDashboard';

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

const dashboardStoreMock = vi.hoisted(() => ({
  creative: { status: 'loaded' as const, data: [], error: undefined },
  campaign: { status: 'loaded' as const, data: { summary: { currency: 'USD' }, rows: [] }, error: undefined },
  getCreativeRowsForSelectedParish: () =>
    [] as Array<{
      id: string;
      name: string;
      platform: string;
      spend: number;
      impressions: number;
      clicks: number;
      conversions: number;
      roas: number;
      reach?: number;
    }>,
  availability: { creative: { status: 'available' as const, reason: null } },
  filters: { accountId: '' },
  loadAll: vi.fn(),
}));

const datasetStoreMock = vi.hoisted(() => ({
  mode: 'dummy' as string,
  source: '' as string,
  liveReason: null as string | null,
  liveDetail: null as string | null,
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

vi.mock('../../state/useDashboardStore', () => {
  const fn = (selector?: (s: typeof dashboardStoreMock) => unknown) =>
    selector ? selector(dashboardStoreMock) : dashboardStoreMock;
  fn.getState = () => dashboardStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../state/useDatasetStore', () => ({
  useDatasetStore: (selector?: (s: typeof datasetStoreMock) => unknown) =>
    selector ? selector(datasetStoreMock) : datasetStoreMock,
}));

vi.mock('../../lib/datasetStatus', () => ({
  messageForLiveDatasetReason: () => 'Live dataset unavailable.',
  titleForLiveDatasetReason: () => 'Dataset blocked',
}));

vi.mock('../../lib/format', () => ({
  formatCurrency: (v: number) => `$${v}`,
  formatNumber: (v: number) => String(v),
  formatRatio: (v: number) => String(v),
}));

vi.mock('../../components/CreativeTable', () => ({
  __esModule: true,
  default: () => <div data-testid="creative-table" />,
}));

// S4a: mock viz-kit primitives for deterministic assertions.
vi.mock('../../components/viz', () => ({
  KpiTile: ({ label, value }: { label: string; value: number | null }) => (
    <div data-testid="kpi-tile">
      {label}: {value === null || value === undefined ? '—' : String(value)}
    </div>
  ),
  BubbleScatter: ({ data, ariaLabel }: { data: unknown[]; ariaLabel: string }) => (
    <div data-testid="bubble-scatter" role="img" aria-label={ariaLabel} data-count={data.length} />
  ),
  PieComposition: ({ data, ariaLabel }: { data: unknown[]; ariaLabel: string }) => (
    <div data-testid="pie-composition" role="img" aria-label={ariaLabel} data-slices={data.length} />
  ),
  VizDataTable: ({ data, caption }: { data: unknown[]; caption?: string }) => (
    <div data-testid="viz-data-table" data-rows={data.length}>
      {caption ?? 'Creative drill-down'}
    </div>
  ),
  ChartSkeleton: () => <div data-testid="chart-skeleton" />,
}));

vi.mock('../../components/DashboardState', () => ({
  __esModule: true,
  default: ({ title, message, variant }: { title?: string; message?: string; variant: string }) => (
    <div data-testid={`dashboard-state-${variant}`}>
      {title ? <h3>{title}</h3> : null}
      {message ? <p>{message}</p> : null}
    </div>
  ),
}));

vi.mock('../../components/ui/Card', () => ({
  __esModule: true,
  default: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div><h2>{title}</h2>{children}</div>
  ),
}));

vi.mock('../../components/ui/StatCard', () => ({
  __esModule: true,
  default: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}));

describe('CreativeDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.creative = { status: 'loaded', data: [], error: undefined };
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [];
    dashboardStoreMock.availability = { creative: { status: 'available', reason: null } };
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
  });

  it('renders creative leaderboard heading when data is available', () => {
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [
      { spend: 100, impressions: 5000, clicks: 50, conversions: 5, roas: 2.0 },
    ];

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Creative leaderboard' })).toBeInTheDocument();
    expect(screen.getByTestId('creative-table')).toBeInTheDocument();
  });

  it('shows empty state when no creative data', () => {
    dashboardStoreMock.creative = { status: 'loaded', data: null as never, error: undefined };
    dashboardStoreMock.availability = { creative: { status: 'empty' as never, reason: null } };

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No creative insights yet')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    dashboardStoreMock.creative = { status: 'loading' as const, data: undefined as never, error: undefined };

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Loading creative performance...')).toBeInTheDocument();
  });

  // S4a: new viz-kit assertions — KpiTile x4 strip when rows populated.
  it('renders KpiTile x4 strip when creative rows are populated', () => {
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [
      {
        id: 'c1',
        name: 'Creative One',
        platform: 'facebook',
        spend: 200,
        impressions: 10000,
        clicks: 150,
        conversions: 10,
        roas: 2.0,
        reach: 8000,
      },
      {
        id: 'c2',
        name: 'Creative Two',
        platform: 'instagram',
        spend: 300,
        impressions: 15000,
        clicks: 200,
        conversions: 12,
        roas: 1.5,
        reach: 11000,
      },
    ];

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('group', { name: /creative kpis/i })).toBeInTheDocument();
    const tiles = screen.getAllByTestId('kpi-tile');
    expect(tiles).toHaveLength(4);
  });

  it('renders BubbleScatter with one datum per creative row', () => {
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [
      {
        id: 'c1',
        name: 'Creative One',
        platform: 'facebook',
        spend: 200,
        impressions: 10000,
        clicks: 150,
        conversions: 10,
        roas: 2.0,
        reach: 8000,
      },
      {
        id: 'c2',
        name: 'Creative Two',
        platform: 'instagram',
        spend: 300,
        impressions: 15000,
        clicks: 200,
        conversions: 12,
        roas: 1.5,
        reach: 11000,
      },
    ];

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    const scatter = screen.getByTestId('bubble-scatter');
    expect(scatter).toBeInTheDocument();
    expect(scatter.getAttribute('data-count')).toBe('2');
  });

  it('renders PieComposition with one slice per unique platform', () => {
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [
      {
        id: 'c1',
        name: 'Creative One',
        platform: 'facebook',
        spend: 200,
        impressions: 10000,
        clicks: 150,
        conversions: 10,
        roas: 2.0,
        reach: 8000,
      },
      {
        id: 'c2',
        name: 'Creative Two',
        platform: 'instagram',
        spend: 300,
        impressions: 15000,
        clicks: 200,
        conversions: 12,
        roas: 1.5,
        reach: 11000,
      },
      {
        id: 'c3',
        name: 'Creative Three',
        platform: 'facebook',
        spend: 100,
        impressions: 5000,
        clicks: 80,
        conversions: 4,
        roas: 1.8,
        reach: 4000,
      },
    ];

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    const pie = screen.getByTestId('pie-composition');
    expect(pie).toBeInTheDocument();
    // 2 unique platforms (facebook + instagram) aggregated from 3 rows.
    expect(pie.getAttribute('data-slices')).toBe('2');
  });

  it('renders VizDataTable drill-down with one row per creative', () => {
    dashboardStoreMock.getCreativeRowsForSelectedParish = () => [
      {
        id: 'c1',
        name: 'Creative One',
        platform: 'facebook',
        spend: 200,
        impressions: 10000,
        clicks: 150,
        conversions: 10,
        roas: 2.0,
        reach: 8000,
      },
      {
        id: 'c2',
        name: 'Creative Two',
        platform: 'instagram',
        spend: 300,
        impressions: 15000,
        clicks: 200,
        conversions: 12,
        roas: 1.5,
        reach: 11000,
      },
    ];

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    const table = screen.getByTestId('viz-data-table');
    expect(table).toBeInTheDocument();
    expect(table.getAttribute('data-rows')).toBe('2');
  });

  it('preserves 3-branch empty-state: no_matching_filters variant', () => {
    dashboardStoreMock.creative = { status: 'loaded', data: null as never, error: undefined };
    dashboardStoreMock.availability = {
      creative: { status: 'empty' as never, reason: 'no_matching_filters' as never },
    };

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No creatives match this view')).toBeInTheDocument();
  });

  it('preserves 3-branch empty-state: no_recent_data variant', () => {
    dashboardStoreMock.creative = { status: 'loaded', data: null as never, error: undefined };
    dashboardStoreMock.availability = {
      creative: { status: 'empty' as never, reason: 'no_recent_data' as never },
    };

    render(
      <MemoryRouter>
        <CreativeDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No recent reportable data')).toBeInTheDocument();
  });
});
