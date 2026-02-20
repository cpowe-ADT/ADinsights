import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import KPIGrid from '../components/KPIGrid';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import TrendChart from '../components/TrendChart';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const METRIC_LABELS: Record<string, string> = {
  page_total_media_view_unique: 'Reach (unique media views)',
  page_media_view: 'Media views',
};

function formatMetricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric;
}

const MetaPageOverviewPage = () => {
  const { pageId = '' } = useParams();
  const [isSyncing, setIsSyncing] = useState(false);

  const {
    pages,
    dashboardStatus,
    overview,
    error,
    loadPages,
    loadOverviewAndTimeseries,
    refreshPage,
    filters,
    setFilters,
  } = useMetaPageInsightsStore((state) => ({
    pages: state.pages,
    dashboardStatus: state.dashboardStatus,
    overview: state.overview,
    error: state.error,
    loadPages: state.loadPages,
    loadOverviewAndTimeseries: state.loadOverviewAndTimeseries,
    refreshPage: state.refreshPage,
    filters: state.filters,
    setFilters: state.setFilters,
  }));

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    if (!pageId) {
      return;
    }
    void loadOverviewAndTimeseries(pageId);
  }, [
    pageId,
    filters.datePreset,
    filters.since,
    filters.until,
    loadOverviewAndTimeseries,
  ]);

  const selectedPage = useMemo(() => pages.find((page) => page.page_id === pageId), [pages, pageId]);
  const selectedMetric = filters.metric || overview?.primary_metric || '';
  const series = overview?.daily_series[selectedMetric] ?? [];

  const syncNow = async () => {
    if (!pageId) {
      return;
    }
    setIsSyncing(true);
    try {
      await refreshPage(pageId);
      await loadOverviewAndTimeseries(pageId);
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Facebook Analytics</p>
        <h1 className="dashboardHeading">{selectedPage?.name ?? 'Facebook Page Overview'}</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/pages">
            All pages
          </Link>
          {pageId ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${pageId}/posts`}>
              Posts
            </Link>
          ) : null}
          <button className="button secondary" type="button" onClick={() => void syncNow()} disabled={isSyncing}>
            {isSyncing ? 'Syncing…' : 'Sync now'}
          </button>
        </div>
      </header>

      {overview ? (
        <div className="meta-sync-meta">
          <p>
            Last synced at: <strong>{overview.last_synced_at ?? 'Never'}</strong>
          </p>
          <div className="meta-overview-metric-picker">
            <label htmlFor="meta-overview-metric">Trend metric</label>
            <select
              id="meta-overview-metric"
              value={selectedMetric}
              onChange={(event) => setFilters({ metric: event.target.value })}
            >
              {Object.keys(overview.metric_availability).map((metric) => (
                <option key={metric} value={metric}>
                  {formatMetricLabel(metric)}
                </option>
              ))}
            </select>
            <MetricAvailabilityBadge metric={selectedMetric} availability={overview.metric_availability[selectedMetric]} />
          </div>
        </div>
      ) : null}

      {dashboardStatus === 'loading' ? <div className="dashboard-state">Loading overview…</div> : null}
      {dashboardStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load page overview"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => pageId && void loadOverviewAndTimeseries(pageId)}
          className="panel"
        />
      ) : null}

      {dashboardStatus === 'loaded' && overview ? (
        <>
          <KPIGrid kpis={overview.kpis} metricAvailability={overview.metric_availability} />
          {series.length > 0 ? <TrendChart title={`${formatMetricLabel(selectedMetric)} trend`} points={series} /> : null}
          {series.length === 0 ? (
            <div className="panel meta-warning-panel" role="status">
              <h3>No trend points available</h3>
              <p>Try another metric or trigger sync.</p>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
};

export default MetaPageOverviewPage;
