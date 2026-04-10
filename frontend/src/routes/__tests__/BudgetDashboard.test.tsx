import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BudgetDashboard from '../BudgetDashboard';

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

const dashboardStoreMock = vi.hoisted(() => ({
  budget: { status: 'loaded' as const, data: [], error: undefined },
  campaign: { status: 'loaded' as const, data: { summary: { currency: 'USD' }, rows: [] }, error: undefined },
  getBudgetRowsForSelectedParish: () => [] as Array<{ pacingPercent: number; windowBudget?: number; monthlyBudget: number; projectedSpend: number }>,
  availability: { budget: { status: 'available' as const, reason: null } },
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
}));

vi.mock('../../components/BudgetPacingList', () => ({
  __esModule: true,
  default: () => <div data-testid="budget-pacing-list" />,
}));

vi.mock('../../components/FilterStatus', () => ({
  __esModule: true,
  default: () => <div data-testid="filter-status" />,
}));

vi.mock('../../components/ui/StatCard', () => ({
  __esModule: true,
  default: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}));

describe('BudgetDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.budget = { status: 'loaded', data: [], error: undefined };
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [];
    dashboardStoreMock.availability = { budget: { status: 'available', reason: null } };
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
  });

  it('renders budget pacing heading when data is available', () => {
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [
      { pacingPercent: 1.0, monthlyBudget: 1000, projectedSpend: 950 },
    ];

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Budget pacing' })).toBeInTheDocument();
    expect(screen.getByTestId('budget-pacing-list')).toBeInTheDocument();
  });

  it('shows empty state when budget is unavailable', () => {
    dashboardStoreMock.availability = {
      budget: { status: 'empty' as never, reason: 'budget_unavailable' },
    };
    dashboardStoreMock.budget = { status: 'loaded', data: null as never, error: undefined };

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Budgets are unavailable for this view')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    dashboardStoreMock.budget = { status: 'loading' as const, data: undefined as never, error: undefined };

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Loading budget pacing...')).toBeInTheDocument();
  });
});
