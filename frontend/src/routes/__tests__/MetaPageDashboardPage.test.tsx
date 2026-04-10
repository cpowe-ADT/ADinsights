import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MetaPageDashboardPage from '../MetaPageDashboardPage';

const storeMock = vi.hoisted(() => ({
  dashboardStatus: 'loaded' as string,
  pages: [{ page_id: 'p1', name: 'Test Page', can_analyze: true }],
  selectedPageId: 'p1',
  setSelectedPageId: vi.fn(),
  filters: { datePreset: 'last_28d', since: '2026-03-01', until: '2026-03-28', metric: 'page_impressions', period: 'day', showAllMetrics: false },
  setFilters: vi.fn(),
  overview: { metrics: [], cards: [{ label: 'Impressions', value: 1200 }] },
  timeseries: { metric: 'page_impressions', points: [{ date: '2026-03-01', value: 100 }] },
  error: null as string | null,
  loadPages: vi.fn(),
  loadOverviewAndTimeseries: vi.fn(),
  refreshPage: vi.fn(),
}));

vi.mock('../../state/useMetaPageInsightsStore', () => ({
  default: (selector: (s: typeof storeMock) => unknown) => selector(storeMock),
}));

vi.mock('../../components/meta/DateRangePicker', () => ({
  default: () => <div data-testid="date-range-picker" />,
}));
vi.mock('../../components/meta/KpiCards', () => ({
  default: ({ cards }: { cards: { label: string; value: number }[] }) => (
    <div data-testid="kpi-cards">{cards.map((c) => c.label).join(',')}</div>
  ),
}));
vi.mock('../../components/meta/MetricPicker', () => ({
  default: () => <div data-testid="metric-picker" />,
}));
vi.mock('../../components/meta/TimeseriesChart', () => ({
  default: ({ title }: { title: string }) => <div data-testid="timeseries-chart">{title}</div>,
}));
vi.mock('../../components/EmptyState', () => ({
  default: ({ title }: { title: string }) => <div data-testid="empty-state">{title}</div>,
}));

const renderPage = (pageId = 'p1') =>
  render(
    <MemoryRouter initialEntries={[`/dashboards/meta/pages/${pageId}`]}>
      <Routes>
        <Route path="/dashboards/meta/pages/:pageId" element={<MetaPageDashboardPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('MetaPageDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeMock.dashboardStatus = 'loaded';
    storeMock.pages = [{ page_id: 'p1', name: 'Test Page', can_analyze: true }];
    storeMock.overview = { metrics: [], cards: [{ label: 'Impressions', value: 1200 }] };
    storeMock.timeseries = { metric: 'page_impressions', points: [{ date: '2026-03-01', value: 100 }] };
    storeMock.error = null;
  });

  it('renders the page heading', () => {
    renderPage();
    expect(screen.getByText('Facebook Page Insights')).toBeInTheDocument();
  });

  it('renders KPI cards and timeseries chart when loaded', () => {
    renderPage();
    expect(screen.getByTestId('kpi-cards')).toBeInTheDocument();
    expect(screen.getByTestId('timeseries-chart')).toBeInTheDocument();
  });

  it('shows error state via EmptyState when dashboardStatus is error', () => {
    storeMock.dashboardStatus = 'error';
    storeMock.error = 'Something broke';
    storeMock.overview = null as unknown as typeof storeMock.overview;
    storeMock.timeseries = null as unknown as typeof storeMock.timeseries;
    renderPage();
    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    storeMock.dashboardStatus = 'loading';
    storeMock.overview = null as unknown as typeof storeMock.overview;
    storeMock.timeseries = null as unknown as typeof storeMock.timeseries;
    renderPage();
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
  });

  it('shows warning when page cannot analyze', () => {
    storeMock.pages = [{ page_id: 'p1', name: 'Test Page', can_analyze: false }];
    renderPage();
    expect(screen.getByText('Page is not eligible for insights')).toBeInTheDocument();
  });

  it('calls loadPages on mount', () => {
    renderPage();
    expect(storeMock.loadPages).toHaveBeenCalled();
  });
});
