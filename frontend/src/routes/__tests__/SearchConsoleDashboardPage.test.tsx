import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SearchConsoleDashboardPage from '../SearchConsoleDashboardPage';

const webAnalyticsMocks = vi.hoisted(() => ({
  fetchSearchConsoleWebRows: vi.fn(),
}));

vi.mock('../../lib/webAnalytics', () => ({
  fetchSearchConsoleWebRows: webAnalyticsMocks.fetchSearchConsoleWebRows,
}));

// Mock viz kit primitives so we can assert presence via data-testid without
// depending on recharts internals.
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
    TrendLine: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-trend-line" aria-label={ariaLabel} />
    ),
    PieComposition: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-pie-composition" aria-label={ariaLabel} />
    ),
    VizDataTable: ({ title }: { title: string }) => (
      <div data-testid="viz-data-table">{title}</div>
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => (
      <div data-testid="viz-a11y-toggle">{chart}</div>
    ),
    EmptyState: ({
      title,
      message,
      reasonCode,
    }: {
      title: string;
      message?: string;
      reasonCode?: string;
    }) => (
      <div data-testid="empty-state" data-reason={reasonCode}>
        <h3>{title}</h3>
        {message ? <p>{message}</p> : null}
      </div>
    ),
  };
});

const okPayload = {
  source: 'search_console' as const,
  status: 'ok' as const,
  count: 2,
  rows: [
    {
      date_day: '2026-04-09',
      site_url: 'https://example.com',
      country: 'JM',
      device: 'MOBILE',
      query: 'marketing analytics jamaica',
      page: '/dashboards',
      clicks: 42,
      impressions: 1200,
      ctr: 0.035,
      position: 4.2,
    },
    {
      date_day: '2026-04-08',
      site_url: 'https://example.com',
      country: 'US',
      device: 'DESKTOP',
      query: 'ad insights tool',
      page: '/home',
      clicks: 18,
      impressions: 800,
      ctr: 0.0225,
      position: 6.1,
    },
  ],
};

describe('SearchConsoleDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValue(okPayload);
  });

  it('renders KpiTile strip, dual-axis TrendLine, PieComposition and VizDataTable blocks', async () => {
    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalled();
    });

    expect(screen.getByRole('heading', { name: 'Search Console' })).toBeInTheDocument();

    // T1-05: deferred-ingestion notice is always visible above the data.
    const notice = screen.getByTestId('search-console-deferred-notice');
    expect(notice).toBeInTheDocument();
    expect(notice.getAttribute('data-reason')).toBe('search_console_ingestion_deferred');
    expect(notice.textContent).toMatch(/coming soon/i);

    // KPI strip (Total Clicks / Total Impressions / Average CTR / Average Position)
    await waitFor(() => {
      expect(screen.getAllByTestId('kpi-tile')).toHaveLength(4);
    });
    expect(screen.getByLabelText('Total Clicks')).toBeInTheDocument();
    expect(screen.getByLabelText('Total Impressions')).toBeInTheDocument();
    expect(screen.getByLabelText('Average CTR')).toBeInTheDocument();
    expect(screen.getByLabelText('Average Position')).toBeInTheDocument();

    // Trend + Pie + Table viz blocks
    expect(screen.getByTestId('viz-trend-line')).toBeInTheDocument();
    expect(screen.getByTestId('viz-pie-composition')).toBeInTheDocument();
    expect(screen.getByTestId('viz-data-table')).toBeInTheDocument();
  });

  it('R3: uses the dedicated Search Console endpoint and never calls /metrics/combined/', async () => {
    // R3: Web page must never call /metrics/combined/.
    // The page must go through fetchSearchConsoleWebRows (which hits
    // /analytics/web/search-console/) and must NOT trigger any window.fetch
    // call into the combined-metrics endpoint.
    const fetchSpy = vi.spyOn(window, 'fetch');
    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalled();
    });
    const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes('/metrics/combined/'))).toBe(false);
    // The dedicated endpoint is encapsulated inside the mocked wrapper; we
    // assert the wrapper was invoked as the explicit R3 signal.
    expect(webAnalyticsMocks.fetchSearchConsoleWebRows).toHaveBeenCalledTimes(1);
  });

  it('renders search_console_ingestion_deferred empty state when backend reports unavailable', async () => {
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValueOnce({
      source: 'search_console',
      status: 'unavailable',
      count: 0,
      rows: [],
      detail: 'Search Console not configured',
    });

    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByTestId('empty-state').getAttribute('data-reason')).toBe(
      'search_console_ingestion_deferred',
    );
    expect(screen.getByText(/Search Console ingestion deferred/i)).toBeInTheDocument();
  });

  it('renders no_data_for_range empty state when zero rows returned', async () => {
    webAnalyticsMocks.fetchSearchConsoleWebRows.mockResolvedValueOnce({
      source: 'search_console',
      status: 'ok',
      count: 0,
      rows: [],
    });

    render(
      <MemoryRouter>
        <SearchConsoleDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByTestId('empty-state').getAttribute('data-reason')).toBe(
      'no_data_for_range',
    );
  });
});
