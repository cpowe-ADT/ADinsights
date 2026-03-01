import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import KPIGrid from '../components/KPIGrid';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import TrendChart from '../components/TrendChart';
import MetaPageExportHistory from '../components/meta/MetaPageExportHistory';
import MetaPagesFilterBar from '../components/meta/MetaPagesFilterBar';
import MetricPicker from '../components/meta/MetricPicker';
import useMetaPageExports from '../hooks/useMetaPageExports';
import { toMetaPageDateParams } from '../lib/metaPageDateRange';
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
  const navigate = useNavigate();
  const [isSyncing, setIsSyncing] = useState(false);
  const { jobs: exportJobs, error: exportError, status: exportStatus, refresh: refreshExports, createExport, download } =
    useMetaPageExports(pageId);

  const {
    pages,
    metrics,
    dashboardStatus,
    overview,
    timeseries,
    error,
    loadPages,
    loadMetricRegistry,
    loadOverviewAndTimeseries,
    loadTimeseries,
    refreshPage,
    filters,
    setFilters,
  } = useMetaPageInsightsStore((state) => ({
    pages: state.pages,
    metrics: state.metrics,
    dashboardStatus: state.dashboardStatus,
    overview: state.overview,
    timeseries: state.timeseries,
    error: state.error,
    loadPages: state.loadPages,
    loadMetricRegistry: state.loadMetricRegistry,
    loadOverviewAndTimeseries: state.loadOverviewAndTimeseries,
    loadTimeseries: state.loadTimeseries,
    refreshPage: state.refreshPage,
    filters: state.filters,
    setFilters: state.setFilters,
  }));

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    void loadMetricRegistry();
  }, [loadMetricRegistry]);

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
  const selectedMetric = filters.metric || overview?.primary_metric || 'page_post_engagements';
  const getSupportedPeriods = useCallback(
    (metricKey: string) => {
      const option = metrics.page.find((candidate) => candidate.metric_key === metricKey);
      if (option?.supported_periods?.length) {
        return option.supported_periods;
      }
      return ['day', 'week', 'days_28'];
    },
    [metrics.page],
  );
  const supportedPeriods = getSupportedPeriods(selectedMetric);

  useEffect(() => {
    if (supportedPeriods.length === 0) {
      return;
    }
    if (!supportedPeriods.includes(filters.period)) {
      const nextPeriod = supportedPeriods[0] ?? 'day';
      setFilters({ period: nextPeriod });
      if (pageId) {
        void loadTimeseries(pageId);
      }
    }
  }, [filters.period, loadTimeseries, pageId, setFilters, supportedPeriods]);

  const timeseriesPoints = useMemo(
    () =>
      (timeseries?.points ?? []).map((point) => ({
        date: point.end_time.slice(0, 10),
        value: point.value,
      })),
    [timeseries?.points],
  );

  const handleMetricChange = (metric: string) => {
    const metricPeriods = getSupportedPeriods(metric);
    const nextPeriod = metricPeriods.includes(filters.period) ? filters.period : (metricPeriods[0] ?? 'day');
    setFilters({ metric, period: nextPeriod });
    if (pageId) {
      void loadTimeseries(pageId);
    }
  };

  const handlePeriodChange = (period: string) => {
    setFilters({ period });
    if (pageId) {
      void loadTimeseries(pageId);
    }
  };

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

  const runExport = async (format: 'csv' | 'pdf' | 'png') => {
    if (!pageId) {
      return;
    }
    await createExport({
      export_format: format,
      ...toMetaPageDateParams({
        datePreset: filters.datePreset,
        since: filters.since,
        until: filters.until,
      }),
      trend_metric: selectedMetric,
      trend_period: filters.period,
      posts_metric: 'post_media_view',
      posts_sort: 'metric_desc',
      posts_limit: 10,
    });
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
          <button className="button tertiary" type="button" onClick={() => void runExport('csv')} disabled={exportStatus === 'loading'}>
            Export CSV
          </button>
          <button className="button tertiary" type="button" onClick={() => void runExport('pdf')} disabled={exportStatus === 'loading'}>
            Export PDF
          </button>
          <button className="button tertiary" type="button" onClick={() => void runExport('png')} disabled={exportStatus === 'loading'}>
            Export PNG
          </button>
        </div>
      </header>

      <MetaPagesFilterBar
        pages={pages}
        selectedPageId={pageId}
        datePreset={filters.datePreset}
        since={filters.since}
        until={filters.until}
        onChangePage={(nextPageId) => navigate(`/dashboards/meta/pages/${nextPageId}/overview`)}
        onChangeDatePreset={(preset) => setFilters({ datePreset: preset })}
        onChangeSince={(value) => setFilters({ since: value })}
        onChangeUntil={(value) => setFilters({ until: value })}
      />

      {overview ? (
        <div className="meta-sync-meta">
          <p>
            Last synced at: <strong>{overview.last_synced_at ?? 'Never'}</strong>
          </p>
          <MetricPicker
            metrics={metrics.page}
            selectedMetric={selectedMetric}
            showAllMetrics={filters.showAllMetrics}
            onMetricChange={handleMetricChange}
            onToggleAllMetrics={(showAll) => setFilters({ showAllMetrics: showAll })}
          />
          <label className="dashboard-field" style={{ marginTop: '0.75rem' }}>
            <span className="dashboard-field__label">Period</span>
            <select
              value={filters.period}
              onChange={(event) => handlePeriodChange(event.target.value)}
            >
              {supportedPeriods.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>
          <div style={{ marginTop: '0.5rem' }}>
            <MetricAvailabilityBadge
              metric={selectedMetric}
              availability={overview.metric_availability[selectedMetric]}
            />
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
          {timeseriesPoints.length > 0 ? (
            <TrendChart title={`${formatMetricLabel(selectedMetric)} trend`} points={timeseriesPoints} />
          ) : null}
          {timeseriesPoints.length === 0 ? (
            <div className="panel meta-warning-panel" role="status">
              <h3>No trend points available</h3>
              <p>Try another metric or trigger sync.</p>
            </div>
          ) : null}
        </>
      ) : null}

      <MetaPageExportHistory
        jobs={exportJobs}
        error={exportError}
        isLoading={exportStatus === 'loading'}
        onRefresh={() => void refreshExports()}
        onDownload={(jobId) => void download(jobId)}
      />
    </section>
  );
};

export default MetaPageOverviewPage;
