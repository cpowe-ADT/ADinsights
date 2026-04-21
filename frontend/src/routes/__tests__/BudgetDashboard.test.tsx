import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BudgetDashboard from '../BudgetDashboard';

const authMock = vi.hoisted(() => ({
  tenantId: 't1',
  user: { email: 'test@example.com', role: 'admin', tenant_id: 't1' },
}));

type BudgetRowLite = {
  id: string;
  campaignName: string;
  platform?: string;
  monthlyBudget: number;
  windowBudget?: number;
  spendToDate: number;
  projectedSpend: number;
  pacingPercent: number;
};

const dashboardStoreMock = vi.hoisted(() => ({
  budget: {
    status: 'loaded' as string,
    data: [] as unknown,
    error: undefined as string | undefined,
    errorKind: undefined as string | undefined,
  },
  campaign: {
    status: 'loaded' as string,
    data: { summary: { currency: 'USD' }, trend: [], rows: [] } as unknown,
    error: undefined as string | undefined,
  },
  getBudgetRowsForSelectedParish: () => [] as BudgetRowLite[],
  availability: { budget: { status: 'available' as string, reason: null as string | null } } as unknown,
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

vi.mock('../../components/BudgetPacingList', () => ({
  __esModule: true,
  default: () => <div data-testid="budget-pacing-list" />,
}));

vi.mock('../../components/FilterStatus', () => ({
  __esModule: true,
  default: () => <div data-testid="filter-status" />,
}));

vi.mock('../../components/viz', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../components/viz');
  return {
    ...actual,
    KpiTile: ({ label, value }: { label: string; value: number | null }) => (
      <article data-testid="kpi-tile" aria-label={label}>
        <p>{label}</p>
        <strong>{value ?? '—'}</strong>
      </article>
    ),
    DistributionBar: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-distribution-bar" aria-label={ariaLabel} />
    ),
    TrendLine: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-trend-line" aria-label={ariaLabel} />
    ),
    VizDataTable: ({
      data,
    }: {
      data: Array<{ id: string; label: string; pacing: number; hasBudget: boolean }>;
    }) => (
      <div data-testid="viz-data-table">
        {data.map((row) => (
          <div key={row.id} data-testid="viz-data-table-row">
            <span>{row.label}</span>
            {row.hasBudget ? (
              <span data-testid="pacing-risk-chip" data-variant="ok">
                {Math.round(row.pacing * 100)}%
              </span>
            ) : null}
          </div>
        ))}
      </div>
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => (
      <div data-testid="viz-a11y-toggle">{chart}</div>
    ),
  };
});

describe('BudgetDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dashboardStoreMock.budget = { status: 'loaded', data: [], error: undefined, errorKind: undefined };
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [];
    dashboardStoreMock.availability = { budget: { status: 'available', reason: null } };
    datasetStoreMock.mode = 'dummy';
    datasetStoreMock.liveReason = null;
  });

  it('renders KpiTile strip and viz-kit blocks when data is available', () => {
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [
      {
        id: 'c1',
        campaignName: 'Spring Launch',
        platform: 'meta_ads',
        pacingPercent: 1.0,
        monthlyBudget: 1000,
        windowBudget: 800,
        spendToDate: 400,
        projectedSpend: 950,
      },
    ];
    dashboardStoreMock.campaign = {
      status: 'loaded',
      data: {
        summary: { currency: 'USD' },
        trend: [{ date: '2026-04-01', spend: 100, conversions: 2, clicks: 10, impressions: 400 }],
        rows: [],
      },
      error: undefined,
    };

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    // KPI strip
    expect(screen.getAllByTestId('kpi-tile').length).toBeGreaterThanOrEqual(3);
    // Paired DistributionBar
    expect(screen.getByTestId('viz-distribution-bar')).toBeInTheDocument();
    // Cumulative trend
    expect(screen.getByTestId('viz-trend-line')).toBeInTheDocument();
    // Drill-down table
    expect(screen.getByTestId('viz-data-table')).toBeInTheDocument();
    // Risk chip present
    expect(screen.getByTestId('pacing-risk-chip')).toBeInTheDocument();
    // Legacy pacing list still renders
    expect(screen.getByTestId('budget-pacing-list')).toBeInTheDocument();
    // Panel heading
    expect(screen.getByRole('heading', { name: 'Budget pacing' })).toBeInTheDocument();
  });

  it('skips paired bar for rows with null budget (budget unavailable)', () => {
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [
      {
        id: 'c1',
        campaignName: 'With Budget',
        platform: 'meta_ads',
        pacingPercent: 1.0,
        monthlyBudget: 1000,
        windowBudget: 800,
        spendToDate: 400,
        projectedSpend: 950,
      },
      {
        id: 'c2',
        campaignName: 'No Budget',
        pacingPercent: 0,
        monthlyBudget: 0,
        spendToDate: 200,
        projectedSpend: 200,
      },
    ];

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Budget unavailable for:/)).toBeInTheDocument();
    // "No Budget" appears twice (VizDataTable row label + footer caption) when a row lacks a budget
    expect(screen.getAllByText(/No Budget/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state when budget is unavailable (FP-BUDG-01 preserved)', () => {
    dashboardStoreMock.availability = {
      budget: { status: 'empty', reason: 'budget_unavailable' },
    };
    dashboardStoreMock.budget = { status: 'loaded', data: null, error: undefined, errorKind: undefined };

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Budgets are unavailable for this view')).toBeInTheDocument();
  });

  it('FP-BUDG-01: does NOT render empty state when availability is undefined (demo adapter)', () => {
    dashboardStoreMock.availability = {};
    dashboardStoreMock.budget = { status: 'loaded', data: [], error: undefined, errorKind: undefined };
    dashboardStoreMock.getBudgetRowsForSelectedParish = () => [
      {
        id: 'c1',
        campaignName: 'Demo',
        platform: 'meta_ads',
        pacingPercent: 1.0,
        monthlyBudget: 1000,
        windowBudget: 800,
        spendToDate: 400,
        projectedSpend: 950,
      },
    ];

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    // Empty-state title should NOT be present; main dashboard should render
    expect(screen.queryByText('Budgets are unavailable for this view')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Budget pacing' })).toBeInTheDocument();
  });

  it('shows loading state', () => {
    dashboardStoreMock.budget = { status: 'loading', data: undefined, error: undefined, errorKind: undefined };

    render(
      <MemoryRouter>
        <BudgetDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText('Loading budget pacing...')).toBeInTheDocument();
  });
});
