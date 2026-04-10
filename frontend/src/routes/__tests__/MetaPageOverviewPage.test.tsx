import { act, render, screen } from '@testing-library/react';
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
        page_total_actions: { supported: false, last_checked_at: null, reason: 'Not available for this Page' },
      },
      kpis: [
        { metric: 'page_post_engagements', resolved_metric: 'page_post_engagements', value: 100, today_value: 10 },
        { metric: 'page_total_actions', resolved_metric: 'page_total_actions', value: 200, today_value: 20 },
      ],
      daily_series: {
        page_post_engagements: [{ date: '2026-01-20', value: 10 }],
      },
      primary_metric: 'page_post_engagements',
      cards: [],
      metrics: [],
      engagement_breakdown: undefined as Record<string, Array<{ type: string; value: number | null }>> | undefined,
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

vi.mock('../../components/EngagementBreakdownPanel', () => ({
  default: ({ breakdown }: { breakdown?: Record<string, Array<{ type: string; value: number | null }>> }) => {
    if (!breakdown) return null;
    const metrics = Object.keys(breakdown).filter((k) => breakdown[k].length > 0);
    if (metrics.length === 0) return null;
    return (
      <section aria-label="Engagement Breakdown">
        <h3>Engagement Breakdown</h3>
        {metrics.map((m) =>
          breakdown[m].map((e) => <span key={`${m}-${e.type}`}>{e.type}: {e.value}</span>),
        )}
      </section>
    );
  },
}));

vi.mock('../../lib/airbyte', () => ({
  loadSocialConnectionStatus: airbyteMocks.loadSocialConnectionStatus,
}));

vi.mock('../../lib/metaPageInsights', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../lib/metaPageInsights')>();
  return {
    ...original,
    listMetaPageExports: vi.fn().mockResolvedValue([]),
    createMetaPageExport: vi.fn().mockResolvedValue({}),
    downloadExportArtifact: vi.fn().mockResolvedValue({ blob: new Blob(), filename: 'export.csv', contentType: 'text/csv' }),
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

  it('renders KPI cards and hides unsupported metric card', async () => {
    let container: HTMLElement;
    await act(async () => {
      const result = render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route path="/dashboards/meta/pages/:pageId/overview" element={<MetaPageOverviewPage />} />
          </Routes>
        </MemoryRouter>,
      );
      container = result.container;
    });

    expect(screen.getAllByText('page_post_engagements').length).toBeGreaterThan(0);
    expect(container!.querySelectorAll('.meta-kpi-card-v2')).toHaveLength(1);
    expect(screen.getByText('Some metrics are not available for this Page.')).toBeInTheDocument();
  });

  it('shows reconnect guidance when page insights permissions are missing', async () => {
    storeMock.state.missingRequiredPermissions = ['pages_read_engagement'];

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/dashboards/meta/pages/page-1/overview']}>
          <Routes>
            <Route path="/dashboards/meta/pages/:pageId/overview" element={<MetaPageOverviewPage />} />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByText('Reconnect Meta to restore insights access')).toBeInTheDocument();
    expect(screen.getByText(/pages_read_engagement/)).toBeInTheDocument();
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
            <Route path="/dashboards/meta/pages/:pageId/overview" element={<MetaPageOverviewPage />} />
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
            <Route path="/dashboards/meta/pages/:pageId/overview" element={<MetaPageOverviewPage />} />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.getByText('Engagement Breakdown')).toBeInTheDocument();
    expect(screen.getByText(/LIKE/)).toBeInTheDocument();
    expect(screen.getByText(/COMMENT/)).toBeInTheDocument();
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
            <Route path="/dashboards/meta/pages/:pageId/overview" element={<MetaPageOverviewPage />} />
          </Routes>
        </MemoryRouter>,
      );
    });

    expect(screen.queryByText('Engagement Breakdown')).not.toBeInTheDocument();
  });
});
