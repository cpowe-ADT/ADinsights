import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPageOverviewPage from '../MetaPageOverviewPage';

const airbyteMocks = vi.hoisted(() => ({
  loadSocialConnectionStatus: vi.fn(),
}));

const storeMock = vi.hoisted(() => ({
  state: {
    pages: [{ id: '1', page_id: 'page-1', name: 'Page 1', can_analyze: true, is_default: true }],
    missingRequiredPermissions: [] as string[],
    metrics: {
      page: [
        {
          metric_key: 'page_post_engagements',
          level: 'PAGE',
          status: 'ACTIVE',
          replacement_metric_key: '',
          supported_periods: ['day', 'week', 'days_28'],
          supports_breakdowns: [],
          title: 'Engagements',
          description: '',
          is_default: true,
        },
      ],
      post: [],
    },
    dashboardStatus: 'loaded',
    overview: {
      page_id: 'page-1',
      name: 'Page 1',
      date_preset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      last_synced_at: '2026-01-28T00:00:00Z',
      metric_availability: {
        page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
        page_total_actions: {
          supported: false,
          last_checked_at: null,
          reason: 'Not available for this Page',
        },
      },
      kpis: [
        {
          metric: 'page_post_engagements',
          resolved_metric: 'page_post_engagements',
          value: 100,
          today_value: 10,
        },
        {
          metric: 'page_total_actions',
          resolved_metric: 'page_total_actions',
          value: 200,
          today_value: 20,
        },
      ],
      daily_series: {
        page_post_engagements: [{ date: '2026-01-20', value: 10 }],
      },
      primary_metric: 'page_post_engagements',
      cards: [],
      metrics: [],
      engagement_breakdown: undefined as
        | Record<string, Array<{ type: string; value: number | null }>>
        | undefined,
    },
    timeseries: {
      page_id: 'page-1',
      metric: 'page_post_engagements',
      period: 'day',
      metric_availability: {
        page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
      },
      points: [{ end_time: '2026-01-20T00:00:00Z', value: 10 }],
    },
    error: undefined,
    loadPages: vi.fn(),
    loadMetricRegistry: vi.fn(),
    loadOverviewAndTimeseries: vi.fn(),
    loadTimeseries: vi.fn(),
    refreshPage: vi.fn(),
    connectOAuthStart: vi.fn(),
    filters: {
      datePreset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      metric: 'page_post_engagements',
      period: 'day',
      showAllMetrics: false,
    },
    setFilters: vi.fn(),
  },
}));

vi.mock('../../state/useMetaPageInsightsStore', () => ({
  default: (selector: (state: typeof storeMock.state) => unknown) => selector(storeMock.state),
}));

vi.mock('../../components/TrendChart', () => ({
  default: () => <div>Trend chart</div>,
}));

vi.mock('../../components/viz', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../components/viz');
  return {
    ...actual,
    TrendLine: ({ ariaLabel }: { ariaLabel: string }) => (
      <div data-testid="viz-trend-line" aria-label={ariaLabel} />
    ),
    PieComposition: ({
      data,
      ariaLabel,
    }: {
      data: Array<{ label: string; value: number }>;
      ariaLabel: string;
    }) => (
      <div data-testid="viz-pie" aria-label={ariaLabel}>
        {data.map((entry) => (
          <span key={entry.label}>
            {entry.label}: {entry.value}
          </span>
        ))}
      </div>
    ),
    KpiTile: ({
      label,
      value,
      isFaded,
    }: {
      label: string;
      value: number | null;
      isFaded?: boolean;
    }) => (
      <article className={`kpi-tile${isFaded ? ' kpi-tile--faded' : ''}`}>
        <p>{label}</p>
        <strong>{value ?? '—'}</strong>
      </article>
    ),
    AccessibleTableToggle: ({ chart }: { chart: React.ReactNode }) => <div>{chart}</div>,
  };
});

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
}));

vi.mock('../../lib/metaPageInsights', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../lib/metaPageInsights')>();
  return {
    ...original,
    listMetaPageExports: vi.fn().mockResolvedValue([]),
    createMetaPageExport: vi.fn().mockResolvedValue({}),
    downloadExportArtifact: vi
      .fn()
      .mockResolvedValue({ blob: new Blob(), filename: 'export.csv', contentType: 'text/csv' }),
  };
});

describe('MetaPageOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeMock.state.missingRequiredPermissions = [];
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T16:00:00Z',
      platforms: [],
    });
  });

  it('renders KpiTile strip with up to 4 tiles and fades unsupported metric tile', async () => {
    let container: HTMLElement;
    await act(async () => {
      const result = render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
      container = result.container;
    });

    // KpiTile-based strip replaces the legacy KPIGrid
    const strip = screen.getByTestId('meta-page-kpi-strip');
    expect(strip).toBeInTheDocument();
    const tiles = strip.querySelectorAll('.kpi-tile');
    expect(tiles.length).toBe(2);
    // Unsupported metric tile gets the faded modifier
    expect(container!.querySelectorAll('.kpi-tile--faded').length).toBe(1);
  });

  it('shows reconnect guidance when page insights permissions are missing', async () => {
    storeMock.state.missingRequiredPermissions = ['pages_read_engagement'];

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByText('Reconnect Meta to restore insights access')).toBeInTheDocument();
    expect(screen.getByText(/pages_read_engagement/)).toBeInTheDocument();
  });

  it('renders a back link to the pages list', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByRole('link', { name: /back to facebook pages/i })).toHaveAttribute(
      'href',
      '/dashboards/meta/pages',
    );
  });

  it('shows restore guidance when marketing access is orphaned', async () => {
    airbyteMocks.loadSocialConnectionStatus.mockResolvedValue({
      generated_at: '2026-04-04T16:00:00Z',
      platforms: [
        {
          platform: 'meta',
          display_name: 'Meta (Facebook)',
          status: 'started_not_complete',
          reason: {
            code: 'orphaned_marketing_access',
            message: 'Restore marketing access to resume ad account reporting.',
          },
          last_checked_at: '2026-04-04T16:00:00Z',
          last_synced_at: null,
          actions: ['recover_marketing_access', 'view'],
          metadata: {
            has_recoverable_marketing_access: true,
          },
        },
      ],
    });

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect((await screen.findAllByText('Restore Meta marketing access')).length).toBeGreaterThan(0);
  });

  it('renders engagement breakdown section when breakdown data is present', async () => {
    storeMock.state.overview = {
      ...storeMock.state.overview!,
      engagement_breakdown: {
        page_post_engagements: [
          { type: 'LIKE', value: 60 },
          { type: 'COMMENT', value: 40 },
        ],
      },
    };

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByText('Engagement Breakdown')).toBeInTheDocument();
    expect(screen.getByText(/LIKE/)).toBeInTheDocument();
    expect(screen.getByText(/COMMENT/)).toBeInTheDocument();
  });

  // C1A-NEW-03: handlePeriodChange must pass period override to loadTimeseries
  it('passes period override to loadTimeseries when period select changes', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    // The period select is labeled "Period" in the overview page
    const periodSelect = screen.getByRole('combobox', { name: /period/i });
    fireEvent.change(periodSelect, { target: { value: 'week' } });

    expect(storeMock.state.loadTimeseries).toHaveBeenCalledWith('page-1', { period: 'week' });
  });

  it('renders TrendLine (viz kit) in place of the legacy TrendChart', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByTestId('viz-trend-line')).toBeInTheDocument();
  });

  it('renders no_page_data empty-state when every KPI value is null', async () => {
    storeMock.state.overview = {
      ...storeMock.state.overview!,
      kpis: [
        {
          metric: 'page_post_engagements',
          resolved_metric: 'page_post_engagements',
          value: null,
          today_value: null,
        },
        {
          metric: 'page_total_actions',
          resolved_metric: 'page_total_actions',
          value: null,
          today_value: null,
        },
      ],
    };

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    const states = screen.getAllByRole('status');
    const noData = states.find((el) => el.getAttribute('data-reason-code') === 'no_page_data');
    expect(noData).toBeDefined();
  });

  it('does not render engagement breakdown when breakdown data is absent', async () => {
    storeMock.state.overview = {
      ...storeMock.state.overview!,
      engagement_breakdown: undefined,
    };

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route
              path="/dashboards/meta/pages/:pageId/overview"
              element={<MetaPageOverviewPage />}
            />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.queryByText('Engagement Breakdown')).not.toBeInTheDocument();
  });
});
