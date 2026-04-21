import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AudienceDashboard from '../AudienceDashboard';

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

const mockDemographics = vi.hoisted(() => ({
  byAge: [
    { ageRange: '25-34', spend: 1000, impressions: 50000, clicks: 2000, conversions: 100, reach: 30000 },
    { ageRange: '35-44', spend: 800, impressions: 40000, clicks: 1500, conversions: 80, reach: 25000 },
  ],
  byGender: [
    { gender: 'female', spend: 1200, impressions: 60000, clicks: 2400, conversions: 120, reach: 36000 },
    { gender: 'male', spend: 600, impressions: 30000, clicks: 1100, conversions: 60, reach: 19000 },
  ],
  byAgeGender: [
    { ageRange: '25-34', gender: 'female', spend: 600, impressions: 30000, clicks: 1200, conversions: 60, reach: 18000 },
    { ageRange: '25-34', gender: 'male', spend: 400, impressions: 20000, clicks: 800, conversions: 40, reach: 12000 },
    { ageRange: '35-44', gender: 'female', spend: 600, impressions: 30000, clicks: 1200, conversions: 60, reach: 18000 },
    { ageRange: '35-44', gender: 'male', spend: 200, impressions: 10000, clicks: 300, conversions: 20, reach: 7000 },
  ],
}));

const mockPlatforms = vi.hoisted(() => ({
  byPlatform: [],
  byDevice: [
    { device: 'mobile', spend: 400, impressions: 80000, clicks: 1800, conversions: 60, reach: 40000 },
    { device: 'desktop', spend: 250, impressions: 35000, clicks: 700, conversions: 20, reach: 20000 },
  ],
  byPlatformDevice: [],
}));

const dashboardStoreMock = vi.hoisted(() => ({
  demographics: { status: 'loaded' as string, data: mockDemographics as unknown, error: undefined as string | undefined },
  platforms: { status: 'loaded' as string, data: mockPlatforms as unknown, error: undefined as string | undefined },
  loadAll: vi.fn(),
  lastSnapshotGeneratedAt: undefined as string | undefined,
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
  formatNumber: (v: number) => String(v),
  formatPercent: (v: number) => `${(v * 100).toFixed(0)}%`,
  formatRelativeTime: () => '5 minutes ago',
  formatAbsoluteTime: () => '2026-04-13 12:00',
  isTimestampStale: () => false,
}));

vi.mock('../../components/AgeGenderPyramid', () => ({
  __esModule: true,
  default: () => <div data-testid="age-gender-pyramid" />,
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

vi.mock('../../components/StatusBanner', () => ({
  __esModule: true,
  default: () => <div data-testid="status-banner" />,
}));

vi.mock('../../components/Skeleton', () => ({
  __esModule: true,
  default: () => <div data-testid="skeleton" />,
}));

vi.mock('../../components/ui/Card', () => ({
  __esModule: true,
  default: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div><h2>{title}</h2>{children}</div>
  ),
}));

vi.mock('../../components/viz', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../components/viz');
  return {
    ...actual,
    KpiTile: ({ label, value, hint }: { label: string; value: number | null; hint?: string }) => (
      <article data-testid="kpi-tile" aria-label={label}>
        <p>{label}</p>
        <strong>{value ?? '—'}</strong>
        {hint ? <span data-testid="kpi-hint">{hint}</span> : null}
      </article>
    ),
    DistributionBar: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-distribution-bar" aria-label={ariaLabel} />
    ),
    PieComposition: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-pie-composition" aria-label={ariaLabel} />
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => (
      <div data-testid="viz-a11y-toggle">{chart}</div>
    ),
  };
});

describe('AudienceDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.demographics = { status: 'loaded', data: mockDemographics, error: undefined };
    dashboardStoreMock.platforms = { status: 'loaded', data: mockPlatforms, error: undefined };
    dashboardStoreMock.lastSnapshotGeneratedAt = undefined;
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
    datasetStoreMock.liveDetail = null;
  });

  it('renders KpiTile strip and viz-kit blocks including Top Device', () => {
    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /audience demographics/i })).toBeInTheDocument();

    const kpiRow = screen.getByRole('group', { name: /audience kpis/i });
    expect(kpiRow).toBeInTheDocument();

    // 4 KpiTiles because platforms.data.byDevice is present → Top Device tile shown
    expect(screen.getAllByTestId('kpi-tile')).toHaveLength(4);
    expect(screen.getByLabelText('Total reach')).toBeInTheDocument();
    expect(screen.getByLabelText('Avg frequency')).toBeInTheDocument();
    expect(screen.getByLabelText('Top age group')).toBeInTheDocument();
    expect(screen.getByLabelText('Top device')).toBeInTheDocument();

    // Composition (gender) via PieComposition
    expect(screen.getAllByTestId('viz-pie-composition').length).toBeGreaterThan(0);
    // Distribution (age + device) via DistributionBar
    expect(screen.getAllByTestId('viz-distribution-bar').length).toBeGreaterThanOrEqual(2);
  });

  it('hides Top Device tile and device block when platforms.data is absent', () => {
    dashboardStoreMock.platforms = { status: 'loaded', data: undefined, error: undefined };

    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    // Only 3 KpiTiles (no Top Device)
    expect(screen.getAllByTestId('kpi-tile')).toHaveLength(3);
    expect(screen.queryByLabelText('Top device')).not.toBeInTheDocument();
    // Only 1 DistributionBar (age only, device block hidden)
    expect(screen.getAllByTestId('viz-distribution-bar')).toHaveLength(1);
  });

  it('FP-AUD-01: shows empty state when byAgeGender and byGender arrays are empty', () => {
    dashboardStoreMock.demographics = {
      status: 'loaded',
      data: { byAge: [], byGender: [], byAgeGender: [] },
      error: undefined,
    };

    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No demographic data for selected range')).toBeInTheDocument();
  });

  it('shows empty state when no demographics data', () => {
    dashboardStoreMock.demographics = { status: 'loaded', data: undefined, error: undefined };

    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No demographic data yet')).toBeInTheDocument();
  });

  it('shows error state on demographics error', () => {
    dashboardStoreMock.demographics = {
      status: 'error',
      data: undefined,
      error: 'Failed to fetch demographics',
    };

    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('dashboard-state-error')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch demographics')).toBeInTheDocument();
  });
});
