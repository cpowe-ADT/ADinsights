import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PlatformDashboard from '../PlatformDashboard';

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

const mockPlatforms = vi.hoisted(() => ({
  byPlatform: [
    { platform: 'facebook', spend: 2000, impressions: 100000, clicks: 4000, conversions: 120, reach: 65000 },
    { platform: 'instagram', spend: 1500, impressions: 80000, clicks: 3500, conversions: 90, reach: 52000 },
  ],
  byDevice: [
    { device: 'mobile_app', spend: 2500, impressions: 130000, clicks: 5500, conversions: 160, reach: 85000 },
    { device: 'desktop', spend: 1000, impressions: 50000, clicks: 2000, conversions: 50, reach: 32000 },
  ],
  byPlatformDevice: [
    { platform: 'facebook', device: 'mobile_app', spend: 1200, impressions: 60000, clicks: 2500, conversions: 75, reach: 39000 },
    { platform: 'facebook', device: 'desktop', spend: 800, impressions: 40000, clicks: 1500, conversions: 45, reach: 26000 },
    { platform: 'instagram', device: 'mobile_app', spend: 1300, impressions: 70000, clicks: 3000, conversions: 85, reach: 46000 },
    { platform: 'instagram', device: 'desktop', spend: 200, impressions: 10000, clicks: 500, conversions: 5, reach: 6000 },
  ],
}));

const dashboardStoreMock = vi.hoisted(() => ({
  platforms: { status: 'loaded' as const, data: mockPlatforms, error: undefined },
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

vi.mock('../../components/PlatformComparisonBars', () => ({
  __esModule: true,
  default: () => <div data-testid="platform-comparison-bars" />,
}));

vi.mock('../../components/DeviceDonut', () => ({
  __esModule: true,
  default: () => <div data-testid="device-donut" />,
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

describe('PlatformDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.platforms = { status: 'loaded', data: mockPlatforms, error: undefined };
    dashboardStoreMock.lastSnapshotGeneratedAt = undefined;
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
    datasetStoreMock.liveDetail = null;
  });

  it('renders heading and KPIs with platforms data', { timeout: 15000 }, () => {
    render(
      <MemoryRouter>
        <PlatformDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /platform & device performance/i })).toBeInTheDocument();

    const kpiRow = screen.getByRole('group', { name: /platform kpis/i });
    expect(kpiRow).toBeInTheDocument();

    // Facebook spend = 2000
    expect(screen.getByText(/Facebook spend: 2000/)).toBeInTheDocument();
    // Instagram spend = 1500
    expect(screen.getByText(/Instagram spend: 1500/)).toBeInTheDocument();
    // Mobile % = mobile_app impressions 130000 / total (130000+50000=180000) ~= 72%
    expect(screen.getByText(/Mobile %: 72%/)).toBeInTheDocument();
    // Top platform by conversions: facebook has 120 vs instagram has 90
    expect(screen.getByText(/Top platform: facebook/)).toBeInTheDocument();
  });

  it('shows empty state when no platforms data', () => {
    dashboardStoreMock.platforms = { status: 'loaded', data: undefined as never, error: undefined };

    render(
      <MemoryRouter>
        <PlatformDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('No platform data yet')).toBeInTheDocument();
  });

  it('shows error state on platforms error', () => {
    dashboardStoreMock.platforms = {
      status: 'error',
      data: undefined,
      error: 'Failed to fetch platform data',
    };

    render(
      <MemoryRouter>
        <PlatformDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('dashboard-state-error')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch platform data')).toBeInTheDocument();
  });
});
