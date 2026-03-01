import { useEffect, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';

import DateRangePicker from '../components/meta/DateRangePicker';
import KpiCards from '../components/meta/KpiCards';
import MetricPicker from '../components/meta/MetricPicker';
import TimeseriesChart from '../components/meta/TimeseriesChart';
import EmptyState from '../components/EmptyState';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';

function formatDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function rangeForPreset(preset: string): { since: string; until: string } {
  const until = new Date();
  const since = new Date(until);
  if (preset === 'today') {
    return { since: formatDate(until), until: formatDate(until) };
  }
  if (preset === 'yesterday') {
    since.setDate(until.getDate() - 1);
    return { since: formatDate(since), until: formatDate(since) };
  }
  if (preset === 'last_7d') {
    since.setDate(until.getDate() - 7);
  } else if (preset === 'last_14d') {
    since.setDate(until.getDate() - 14);
  } else if (preset === 'last_30d') {
    since.setDate(until.getDate() - 30);
  } else if (preset === 'last_90d') {
    since.setDate(until.getDate() - 90);
  } else {
    since.setDate(until.getDate() - 28);
  }
  return { since: formatDate(since), until: formatDate(until) };
}

const MetaPageDashboardPage = () => {
  const { pageId = '' } = useParams();
  const {
    dashboardStatus,
    pages,
    selectedPageId,
    setSelectedPageId,
    filters,
    setFilters,
    overview,
    timeseries,
    error,
    loadPages,
    loadOverviewAndTimeseries,
    refreshPage,
  } = useMetaPageInsightsStore((state) => ({
    dashboardStatus: state.dashboardStatus,
    pages: state.pages,
    selectedPageId: state.selectedPageId,
    setSelectedPageId: state.setSelectedPageId,
    filters: state.filters,
    setFilters: state.setFilters,
    overview: state.overview,
    timeseries: state.timeseries,
    error: state.error,
    loadPages: state.loadPages,
    loadOverviewAndTimeseries: state.loadOverviewAndTimeseries,
    refreshPage: state.refreshPage,
  }));

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    if (!pageId) {
      return;
    }
    if (selectedPageId !== pageId) {
      setSelectedPageId(pageId);
    }
    void loadOverviewAndTimeseries(pageId);
  }, [
    pageId,
    selectedPageId,
    setSelectedPageId,
    loadOverviewAndTimeseries,
    filters.datePreset,
    filters.since,
    filters.until,
    filters.metric,
    filters.period,
  ]);

  const selectedPage = useMemo(() => pages.find((page) => page.page_id === pageId), [pages, pageId]);

  const onRefresh = async () => {
    if (!pageId) {
      return;
    }
    await refreshPage(pageId);
    await loadOverviewAndTimeseries(pageId);
  };

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Dashboards</p>
        <h1 className="dashboardHeading">Facebook Page Insights</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/integrations/meta">
            Back to Meta integration
          </Link>
          {pageId ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${pageId}/posts`}>
              Posts view
            </Link>
          ) : null}
          <button className="button secondary" type="button" onClick={() => void onRefresh()}>
            Refresh data
          </button>
        </div>
      </header>

      {!selectedPage?.can_analyze ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Page is not eligible for insights</h3>
          <p>Select a page where the connecting person can perform ANALYZE.</p>
        </div>
      ) : null}

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <DateRangePicker
          datePreset={filters.datePreset}
          since={filters.since}
          until={filters.until}
          onPresetChange={(value) => {
            const range = rangeForPreset(value);
            setFilters({ datePreset: value, since: range.since, until: range.until });
          }}
          onSinceChange={(value) => setFilters({ since: value })}
          onUntilChange={(value) => setFilters({ until: value })}
        />
        <MetricPicker
          metrics={overview?.metrics ?? []}
          selectedMetric={filters.metric}
          showAllMetrics={filters.showAllMetrics}
          onMetricChange={(metric) => setFilters({ metric })}
          onToggleAllMetrics={(showAll) => setFilters({ showAllMetrics: showAll })}
        />
      </div>

      {dashboardStatus === 'loading' ? <div className="dashboard-state">Loading dashboard…</div> : null}
      {dashboardStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load page dashboard"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => pageId && void loadOverviewAndTimeseries(pageId)}
          className="panel"
        />
      ) : null}

      {dashboardStatus === 'loaded' && overview && overview.cards.length > 0 ? <KpiCards cards={overview.cards} /> : null}

      {dashboardStatus === 'loaded' && timeseries && timeseries.points.length > 0 ? (
        <TimeseriesChart title={`${timeseries.metric} trend`} points={timeseries.points} />
      ) : null}

      {dashboardStatus === 'loaded' && (!timeseries || timeseries.points.length === 0) ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>No insights data yet</h3>
          <p>
            Insights are available only for pages with at least 100 likes and typically update once every 24 hours.
            Verify permissions and run a refresh.
          </p>
        </div>
      ) : null}
    </section>
  );
};

export default MetaPageDashboardPage;
