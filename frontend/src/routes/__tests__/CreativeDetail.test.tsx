import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CreativeDetail from '../CreativeDetail';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ creativeId: 'cr-1' }),
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
    data: { summary: { currency: 'USD' }, rows: [] },
    error: undefined,
  },
  creative: {
    status: 'loaded' as const,
    data: [
      {
        id: 'cr-1',
        name: 'Test Creative',
        platform: 'Meta',
        campaignId: 'cmp-1',
        campaignName: 'Test Campaign',
        parishes: ['Kingston'],
        spend: 500,
        impressions: 25000,
        clicks: 100,
        conversions: 10,
        roas: 2.0,
        ctr: 0.004,
        thumbnailUrl: null,
      },
    ],
    error: undefined,
  },
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
    <div><h2>{title}</h2>{children}</div>
  ),
}));

vi.mock('../../components/ui/StatCard', () => ({
  __esModule: true,
  default: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}));

describe('CreativeDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders creative name as heading', () => {
    render(
      <MemoryRouter>
        <CreativeDetail />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Test Creative' })).toBeInTheDocument();
    expect(screen.getByText('Creative detail')).toBeInTheDocument();
  });

  it('shows creative not found when creative does not exist', () => {
    dashboardStoreMock.creative = {
      status: 'loaded',
      data: [],
      error: undefined,
    };

    render(
      <MemoryRouter>
        <CreativeDetail />
      </MemoryRouter>,
    );

    expect(screen.getByText('Creative not found')).toBeInTheDocument();
  });
});
