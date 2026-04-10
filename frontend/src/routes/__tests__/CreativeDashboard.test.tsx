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
  getCreativeRowsForSelectedParish: () => [] as Array<{ spend: number; impressions: number; clicks: number; conversions: number; roas: number }>,
  availability: { creative: { status: 'available' as const, reason: null } },
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
});
