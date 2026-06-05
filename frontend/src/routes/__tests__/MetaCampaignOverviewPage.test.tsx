import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaCampaignOverviewPage from '../MetaCampaignOverviewPage';

type CampaignRowMock = {
  id: string;
  name: string;
  external_id: string;
  status: string;
  objective: string;
  account_external_id: string;
  updated_time: string;
  updated_at: string;
};

type InsightRowMock = {
  id: string;
  external_id: string;
  date: string;
  level: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: string;
  campaign_external_id?: string;
};

const metaStoreMock = vi.hoisted(() => ({
  filters: {
    accountId: '',
    search: '',
    status: '',
    since: '',
    until: '',
    level: 'campaign' as string,
  },
  setFilters: vi.fn(),
  accounts: { rows: [] as Array<{ id: string; external_id: string; name: string }> },
  campaigns: {
    status: 'loaded' as string,
    count: 0,
    rows: [] as CampaignRowMock[],
    error: undefined as string | undefined,
    errorCode: undefined as string | undefined,
  },
  insights: {
    status: 'loaded' as string,
    rows: [] as InsightRowMock[],
    count: 0,
  },
  loadAccounts: vi.fn(),
  loadCampaigns: vi.fn(),
  loadInsights: vi.fn(),
}));

vi.mock('../../state/useMetaStore', () => {
  const fn = (selector?: (s: typeof metaStoreMock) => unknown) =>
    selector ? selector(metaStoreMock) : metaStoreMock;
  fn.getState = () => metaStoreMock;
  fn.subscribe = () => () => {};
  return { __esModule: true, default: fn };
});

vi.mock('../../components/EmptyState', () => ({
  __esModule: true,
  default: ({
    title,
    message,
    reasonCode,
  }: {
    title: string;
    message: string;
    reasonCode?: string;
  }) => (
    <div role="status" data-reason-code={reasonCode}>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  ),
}));

vi.mock('../../components/viz', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../components/viz');
  return {
    ...actual,
    KpiTile: ({ label, value }: { label: string; value: number | null }) => (
      <article className="kpi-tile">
        <p>{label}</p>
        <strong>{value ?? '—'}</strong>
      </article>
    ),
    DistributionBar: ({
      data,
      ariaLabel,
    }: {
      data: Array<{ label: string; value: number }>;
      ariaLabel: string;
    }) => (
      <div data-testid="viz-distribution-bar" aria-label={ariaLabel}>
        {data.map((entry, idx) => (
          <span key={entry.label} data-stage-index={idx} data-stage-label={entry.label}>
            {entry.label}:{entry.value}
          </span>
        ))}
      </div>
    ),
    Sparkline: ({ ariaLabel }: { ariaLabel: string }) => (
      <span data-testid="viz-sparkline" aria-label={ariaLabel} />
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => <div>{chart}</div>,
    VizDataTable: ({
      columns,
      data,
    }: {
      columns: Array<{
        header?: string;
        cell?: (ctx: { row: { original: unknown } }) => React.ReactNode;
      }>;
      data: unknown[];
    }) => (
      <table data-testid="viz-data-table">
        <thead>
          <tr>
            {columns.map((col, idx) => (
              <th key={idx}>{typeof col.header === 'string' ? col.header : ''}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {columns.map((col, idx) => (
                <td key={idx}>
                  {typeof col.cell === 'function' ? col.cell({ row: { original: row } }) : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    ),
  };
});

describe('MetaCampaignOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    metaStoreMock.campaigns = {
      status: 'loaded',
      count: 0,
      rows: [],
      error: undefined,
      errorCode: undefined,
    };
    metaStoreMock.insights = { status: 'loaded', rows: [], count: 0 };
    metaStoreMock.filters = {
      accountId: '',
      search: '',
      status: '',
      since: '',
      until: '',
      level: 'campaign',
    };
  });

  it('renders campaign overview heading', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Campaign overview' })).toBeInTheDocument();
  });

  it('shows no campaigns found when rows are empty', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('No campaigns found')).toBeInTheDocument();
  });

  it('shows error state when campaigns fail to load', () => {
    metaStoreMock.campaigns = {
      status: 'error',
      count: 0,
      rows: [],
      error: 'Network error',
      errorCode: undefined,
    };

    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Unable to load campaigns')).toBeInTheDocument();
  });

  it('renders 4 KpiTiles in the rollup strip (Spend, Impressions, Clicks, Conversions)', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    const strip = screen.getByTestId('meta-campaigns-kpi-strip');
    expect(strip.querySelectorAll('.kpi-tile').length).toBe(4);
    expect(screen.getByText('Spend')).toBeInTheDocument();
    expect(screen.getByText('Impressions')).toBeInTheDocument();
    expect(screen.getByText('Clicks')).toBeInTheDocument();
    expect(screen.getByText('Conversions')).toBeInTheDocument();
  });

  it('renders funnel DistributionBar with 3 ordered stages (Impressions → Clicks → Conversions)', () => {
    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    const funnelPanel = screen.getByTestId('meta-campaigns-funnel-panel');
    const bar = funnelPanel.querySelector('[data-testid="viz-distribution-bar"]');
    expect(bar).not.toBeNull();
    const stages = bar!.querySelectorAll('[data-stage-label]');
    expect(stages.length).toBe(3);
    expect(stages[0].getAttribute('data-stage-label')).toBe('Impressions');
    expect(stages[1].getAttribute('data-stage-label')).toBe('Clicks');
    expect(stages[2].getAttribute('data-stage-label')).toBe('Conversions');
  });

  it('limits spend DistributionBar to at most 10 slices', () => {
    metaStoreMock.insights = {
      status: 'loaded',
      count: 12,
      rows: Array.from({ length: 12 }, (_, i) => ({
        id: `i${i}`,
        external_id: `ext${i}`,
        date: '2026-03-01',
        level: 'campaign',
        impressions: 1000,
        clicks: 10,
        conversions: 1,
        spend: String(100 + i),
        campaign_external_id: `c${i}`,
      })),
    };
    metaStoreMock.campaigns = {
      status: 'loaded',
      count: 12,
      rows: Array.from({ length: 12 }, (_, i) => ({
        id: `c${i}`,
        external_id: `c${i}`,
        name: `Campaign ${i}`,
        status: 'ACTIVE',
        objective: 'LINK_CLICKS',
        account_external_id: 'act1',
        updated_time: '2026-03-01',
        updated_at: '2026-03-01',
      })),
      error: undefined,
      errorCode: undefined,
    };

    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    const spendPanel = screen.getByTestId('meta-campaigns-spend-panel');
    const bar = spendPanel.querySelector('[data-testid="viz-distribution-bar"]');
    const slices = bar!.querySelectorAll('[data-stage-label]');
    expect(slices.length).toBeLessThanOrEqual(10);
  });

  it('renders a Sparkline per row in the campaign VizDataTable when insights are present', () => {
    metaStoreMock.insights = {
      status: 'loaded',
      count: 2,
      rows: [
        {
          id: 'i1',
          external_id: 'ext1',
          date: '2026-03-01',
          level: 'campaign',
          impressions: 100,
          clicks: 5,
          conversions: 1,
          spend: '50',
          campaign_external_id: 'c1',
        },
        {
          id: 'i2',
          external_id: 'ext2',
          date: '2026-03-02',
          level: 'campaign',
          impressions: 200,
          clicks: 12,
          conversions: 3,
          spend: '75',
          campaign_external_id: 'c1',
        },
      ],
    };
    metaStoreMock.campaigns = {
      status: 'loaded',
      count: 1,
      rows: [
        {
          id: 'c1',
          external_id: 'c1',
          name: 'Campaign One',
          status: 'ACTIVE',
          objective: 'LINK_CLICKS',
          account_external_id: 'act1',
          updated_time: '2026-03-02',
          updated_at: '2026-03-02',
        },
      ],
      error: undefined,
      errorCode: undefined,
    };

    render(
      <MemoryRouter>
        <MetaCampaignOverviewPage />
      </MemoryRouter>,
    );

    const table = screen.getByTestId('viz-data-table');
    expect(table.querySelectorAll('tbody tr').length).toBe(1);
    expect(screen.getAllByTestId('viz-sparkline').length).toBe(1);
  });

  it('dispatches loadInsights when mounted and level=campaign', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <MetaCampaignOverviewPage />
        </MemoryRouter>,
      );
    });

    expect(metaStoreMock.loadInsights).toHaveBeenCalled();
  });

  it('forces filters.level to "campaign" on mount when a different level is active', async () => {
    metaStoreMock.filters = {
      ...metaStoreMock.filters,
      level: 'ad',
    };

    await act(async () => {
      render(
        <MemoryRouter>
          <MetaCampaignOverviewPage />
        </MemoryRouter>,
      );
    });

    expect(metaStoreMock.setFilters).toHaveBeenCalledWith({ level: 'campaign' });
  });
});
