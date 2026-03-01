import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPageOverviewPage from '../MetaPageOverviewPage';

const storeMock = vi.hoisted(() => ({
  state: {
    pages: [{ id: '1', page_id: 'page-1', name: 'Page 1', can_analyze: true, is_default: true }],
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
});
