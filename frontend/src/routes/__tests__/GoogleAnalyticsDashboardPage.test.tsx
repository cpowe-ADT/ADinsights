import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAnalyticsDashboardPage from '../GoogleAnalyticsDashboardPage';

const webAnalyticsMocks = vi.hoisted(() => ({
  fetchGoogleAnalyticsWebRows: vi.fn(),
}));

vi.mock('../../lib/webAnalytics', () => ({
  fetchGoogleAnalyticsWebRows: webAnalyticsMocks.fetchGoogleAnalyticsWebRows,
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
    VizDataTable: ({ title }: { title: string }) => <div data-testid="viz-data-table">{title}</div>,
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
  source: 'ga4' as const,
  status: 'ok' as const,
  count: 2,
  rows: [
    {
      tenant_id: 'tenant-1',
      date_day: '2026-03-18',
      property_id: '123456789',
      channel_group: 'Paid Search',
      country: 'Jamaica',
      city: 'Kingston',
      campaign_name: 'Spring Launch',
      sessions: 120,
      engaged_sessions: 84,
      conversions: 7,
      purchase_revenue: 5400,
      engagement_rate: 0.7,
      conversion_rate: 0.0583,
    },
    {
      tenant_id: 'tenant-1',
      date_day: '2026-03-17',
      property_id: '123456789',
      channel_group: 'Organic Search',
      country: 'Jamaica',
      city: 'Montego Bay',
      campaign_name: 'Brand Search',
      sessions: 80,
      engaged_sessions: 56,
      conversions: 4,
      purchase_revenue: 2500,
      engagement_rate: 0.7,
      conversion_rate: 0.05,
    },
  ],
};

describe('GoogleAnalyticsDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    webAnalyticsMocks.fetchGoogleAnalyticsWebRows.mockResolvedValue(okPayload);
  });

  it('renders KpiTile strip, TrendLine, PieComposition and VizDataTable blocks', async () => {
    render(
      <MemoryRouter>
        <GoogleAnalyticsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalled();
    });

    expect(screen.getByRole('heading', { name: 'Google Analytics 4' })).toBeInTheDocument();

    // KPI strip (substitution per architect §3: Sessions / Conversions / Revenue / Engagement rate)
    await waitFor(() => {
      expect(screen.getAllByTestId('kpi-tile')).toHaveLength(4);
    });
    expect(screen.getByLabelText('Sessions')).toBeInTheDocument();
    expect(screen.getByLabelText('Conversions')).toBeInTheDocument();
    expect(screen.getByLabelText('Revenue')).toBeInTheDocument();
    expect(screen.getByLabelText('Engagement rate')).toBeInTheDocument();

    // Trend + Pie + Table viz blocks
    expect(screen.getByTestId('viz-trend-line')).toBeInTheDocument();
    expect(screen.getByTestId('viz-pie-composition')).toBeInTheDocument();
    expect(screen.getByTestId('viz-data-table')).toBeInTheDocument();
  });

  it('R3: uses the dedicated GA4 endpoint and never calls /metrics/combined/', async () => {
    // R3: Web page must never call /metrics/combined/.
    // The page must go through fetchGoogleAnalyticsWebRows (which hits
    // /analytics/web/ga4/) and must NOT trigger any window.fetch call into
    // the combined-metrics endpoint.
    const fetchSpy = vi.spyOn(window, 'fetch');
    render(
      <MemoryRouter>
        <GoogleAnalyticsDashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalled();
    });
    const urls = fetchSpy.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes('/metrics/combined/'))).toBe(false);
    // The dedicated endpoint is encapsulated inside the mocked wrapper; we
    // assert the wrapper was invoked as the explicit R3 signal.
    expect(webAnalyticsMocks.fetchGoogleAnalyticsWebRows).toHaveBeenCalledTimes(1);
  });

  it('renders no_ga4_property_selected empty state when backend reports unavailable', async () => {
    webAnalyticsMocks.fetchGoogleAnalyticsWebRows.mockResolvedValueOnce({
      source: 'ga4',
      status: 'unavailable',
      detail: 'Connect a GA4 property from Data Sources.',
      count: 0,
      rows: [],
    });

    render(
      <MemoryRouter>
        <GoogleAnalyticsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByTestId('empty-state').getAttribute('data-reason')).toBe(
      'no_ga4_property_selected',
    );
  });

  it('renders no_data_for_range empty state when zero rows returned', async () => {
    webAnalyticsMocks.fetchGoogleAnalyticsWebRows.mockResolvedValueOnce({
      source: 'ga4',
      status: 'ok',
      count: 0,
      rows: [],
    });

    render(
      <MemoryRouter>
        <GoogleAnalyticsDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByTestId('empty-state').getAttribute('data-reason')).toBe('no_data_for_range');
  });
});
