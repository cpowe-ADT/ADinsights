import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CampaignDetail from '../CampaignDetail';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ campaignId: 'cmp-1' }),
    useNavigate: () => vi.fn(),
  };
});

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

const dashboardStoreMock = vi.hoisted(() => ({
  campaign: {
    status: 'loaded' as const,
    data: {
      summary: { currency: 'USD' },
      rows: [
        {
          id: 'cmp-1',
          name: 'Test Campaign',
          platform: 'Meta',
          status: 'Active',
          objective: 'Awareness',
          parishes: ['Kingston'],
          spend: 1000,
          impressions: 50000,
          clicks: 200,
          conversions: 20,
          roas: 2.5,
          ctr: 0.004,
          cpc: 5,
          cpm: 20,
        },
      ],
    },
    error: undefined,
  },
  creative: { status: 'loaded' as const, data: [], error: undefined },
  loadAll: vi.fn(),
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

vi.mock('../../lib/format', () => ({
  formatCurrency: (v: number) => `$${v}`,
  formatNumber: (v: number) => String(v),
  formatPercent: (v: number) => `${v}%`,
  formatRatio: (v: number) => String(v),
}));

vi.mock('../../components/CreativeTable', () => ({
  __esModule: true,
  default: () => <div data-testid="creative-table" />,
}));

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock('../../components/ErrorState', () => ({
  __esModule: true,
  default: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock('../../components/Skeleton', () => ({
  __esModule: true,
  default: () => <div data-testid="skeleton" />,
}));

vi.mock('../../components/ui/Card', () => ({
  __esModule: true,
  default: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}));

vi.mock('../../components/ui/StatCard', () => ({
  __esModule: true,
  default: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}));

describe('CampaignDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders campaign name as heading', () => {
    render(
      <MemoryRouter future={routerFuture}>
        <CampaignDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Test Campaign' })).toBeInTheDocument();
    expect(screen.getByText('Campaign detail')).toBeInTheDocument();
  });

  it('shows campaign not found when campaign does not exist', () => {
    dashboardStoreMock.campaign = {
      status: 'loaded',
      data: { summary: { currency: 'USD' }, rows: [] },
      error: undefined,
    };

    render(
      <MemoryRouter future={routerFuture}>
        <CampaignDetail />
      </MemoryRouter>,
    );

    expect(screen.getByText('Campaign not found')).toBeInTheDocument();
  });
});
