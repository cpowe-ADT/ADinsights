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

const dashboardStoreMock = vi.hoisted(() => ({
  demographics: { status: 'loaded' as const, data: mockDemographics, error: undefined },
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

vi.mock('../../components/GenderDonut', () => ({
  __esModule: true,
  default: () => <div data-testid="gender-donut" />,
}));

vi.mock('../../components/AgeDistributionBar', () => ({
  __esModule: true,
  default: () => <div data-testid="age-distribution-bar" />,
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

vi.mock('../../components/ui/StatCard', () => ({
  __esModule: true,
  default: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}));

describe('AudienceDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.demographics = { status: 'loaded', data: mockDemographics, error: undefined };
    dashboardStoreMock.lastSnapshotGeneratedAt = undefined;
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
    datasetStoreMock.liveDetail = null;
  });

  it('renders heading and KPIs with demographics data', { timeout: 15000 }, () => {
    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /audience demographics/i })).toBeInTheDocument();

    const kpiRow = screen.getByRole('group', { name: /audience kpis/i });
    expect(kpiRow).toBeInTheDocument();

    // Total reach = 36000 + 19000 = 55000
    expect(screen.getByText(/Total reach: 55000/)).toBeInTheDocument();
    // % Female = 36000 / 55000 ~= 65%
    expect(screen.getByText(/% Female: 65%/)).toBeInTheDocument();
    // Top age group by impressions: 25-34 has 50000 vs 35-44 has 40000
    expect(screen.getByText(/Top age group: 25-34/)).toBeInTheDocument();
    // Total impressions = 50000 + 40000 = 90000
    expect(screen.getByText(/Impressions: 90000/)).toBeInTheDocument();
  });

  it('shows empty state when no demographics data', () => {
    dashboardStoreMock.demographics = { status: 'loaded', data: undefined as never, error: undefined };

    render(
      <MemoryRouter>
        <AudienceDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No demographic data yet')).toBeInTheDocument();
  });

  it('shows error state on demographics error', () => {
    dashboardStoreMock.demographics = {
      status: 'error' as const,
      data: undefined as never,
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
