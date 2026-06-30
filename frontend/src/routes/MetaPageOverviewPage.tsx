import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import Breadcrumbs from '../components/Breadcrumbs';
import EmptyState from '../components/EmptyState';
import MetricAvailabilityBadge from '../components/MetricAvailabilityBadge';
import { AccessibleTableToggle, KpiTile, PieComposition, TrendLine } from '../components/viz';
import MetaPageExportHistory from '../components/meta/MetaPageExportHistory';
import MetaPagesFilterBar from '../components/meta/MetaPagesFilterBar';
import MetricPicker from '../components/meta/MetricPicker';
import useMetaPageExports from '../hooks/useMetaPageExports';
import usePageInsightsSavedViews from '../hooks/usePageInsightsSavedViews';
import { loadSocialConnectionStatus, type SocialPlatformStatusRecord } from '../lib/airbyte';
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
  const [metaStatus, setMetaStatus] = useState<SocialPlatformStatusRecord | null>(null);
  const {
    jobs: exportJobs,
    error: exportError,
    status: exportStatus,
    refresh: refreshExports,
    createExport,
    download,
  } = useMetaPageExports(pageId);
  const {
    views: savedViews,
    save: saveSavedView,
    remove: removeSavedView,
  } = usePageInsightsSavedViews(pageId);

  const {
    pages,
    missingRequiredPermissions,
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
    connectOAuthStart,
    filters,
    setFilters,
  } = useMetaPageInsightsStore((state) => ({
    pages: state.pages,
    missingRequiredPermissions: state.missingRequiredPermissions,
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
    connectOAuthStart: state.connectOAuthStart,
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
    let cancelled = false;

    const loadStatus = async () => {
      try {
        const payload = await loadSocialConnectionStatus();
        if (!cancelled) {
          setMetaStatus(payload.platforms.find((row) => row.platform === 'meta') ?? null);
        }
      } catch {
        if (!cancelled) {
          setMetaStatus(null);
        }
      }
    };

    void loadStatus();

    return () => {
      cancelled = true;
    };
  }, []);

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
    filters.compareTo,
    loadOverviewAndTimeseries,
  ]);

  const selectedPage = useMemo(
    () => pages.find((page) => page.page_id === pageId),
    [pages, pageId],
  );
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
  const orphanedMarketingAccess = metaStatus?.reason.code === 'orphaned_marketing_access';

  useEffect(() => {
    if (supportedPeriods.length === 0) {
      return;
    }
    if (!supportedPeriods.includes(filters.period)) {
      const nextPeriod = supportedPeriods[0] ?? 'day';
      setFilters({ period: nextPeriod });
      // No direct loadTimeseries call here — the primary loadOverviewAndTimeseries
      // effect will re-fire when filters.period changes via the store subscription.
    }
  }, [filters.period, pageId, setFilters, supportedPeriods]);

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
    const nextPeriod = metricPeriods.includes(filters.period)
      ? filters.period
      : (metricPeriods[0] ?? 'day');
    setFilters({ metric, period: nextPeriod });
    if (pageId) {
      // C1A-NEW-03: Pass metric/period as overrides so loadTimeseries uses the
      // new values even before Zustand's synchronous setFilters is read by the store.
      void loadTimeseries(pageId, { metric, period: nextPeriod });
    }
  };

  const handlePeriodChange = (period: string) => {
    setFilters({ period });
    if (pageId) {
      // C1A-NEW-03: Pass period as override so loadTimeseries uses the new
      // period value immediately, matching the M16 fix pattern.
      void loadTimeseries(pageId, { period });
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

  const handleSaveView = async () => {
    const name = window.prompt('Name this saved view:');
    if (!name) return;
    await saveSavedView(name, {
      page_id: pageId,
      date_preset: filters.datePreset,
      since: filters.since,
      until: filters.until,
      metric: selectedMetric,
      period: filters.period,
    });
  };

  const handleLoadView = (viewId: string) => {
    const view = savedViews.find((v) => v.id === viewId);
    if (!view) return;
    setFilters({
      datePreset: view.filters.date_preset ?? filters.datePreset,
      since: view.filters.since ?? '',
      until: view.filters.until ?? '',
      metric: view.filters.metric ?? filters.metric,
      period: view.filters.period ?? filters.period,
    });
  };

  const handleDeleteView = async (viewId: string) => {
    await removeSavedView(viewId);
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

  const pageName = selectedPage?.name ?? 'Facebook Page';

  return (
    <section className="dashboardPage">
      <Breadcrumbs
        items={[
          { label: 'Dashboards', to: '/dashboards' },
          { label: 'Facebook Pages', to: '/dashboards/meta/pages' },
          { label: pageName, to: `/dashboards/meta/pages/${pageId}/overview` },
          { label: 'Overview' },
        ]}
      />
      <header className="dashboardPageHeader">
        <h1 className="dashboardHeading">{pageName} Overview</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/pages">
            Back to Facebook pages
          </Link>
          {pageId ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${pageId}/posts`}>
              Posts
            </Link>
          ) : null}
          <button
            className="button secondary"
            type="button"
            onClick={() => void syncNow()}
            disabled={isSyncing}
          >
            {isSyncing ? 'Syncing…' : 'Sync now'}
          </button>
          <button
            className="button tertiary"
            type="button"
            onClick={() => void runExport('csv')}
            disabled={exportStatus === 'loading'}
          >
            Export CSV
          </button>
          <button
            className="button tertiary"
            type="button"
            onClick={() => void runExport('pdf')}
            disabled={exportStatus === 'loading'}
          >
            Export PDF
          </button>
          <button
            className="button tertiary"
            type="button"
            onClick={() => void runExport('png')}
            disabled={exportStatus === 'loading'}
          >
            Export PNG
          </button>
          <button className="button secondary" type="button" onClick={() => void handleSaveView()}>
            Save view
          </button>
          {savedViews.length > 0 ? (
            <select
              className="button tertiary"
              aria-label="Load saved view"
              value=""
              onChange={(e) => {
                if (e.target.value) handleLoadView(e.target.value);
              }}
            >
              <option value="">Load view...</option>
              {savedViews.map((view) => (
                <option key={view.id} value={view.id}>
                  {view.name}
                </option>
              ))}
            </select>
          ) : null}
          {savedViews.length > 0 ? (
            <select
              className="button tertiary"
              aria-label="Delete saved view"
              value=""
              onChange={(e) => {
                if (e.target.value) void handleDeleteView(e.target.value);
              }}
            >
              <option value="">Delete view...</option>
              {savedViews.map((view) => (
                <option key={view.id} value={view.id}>
                  {view.name}
                </option>
              ))}
            </select>
          ) : null}
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

      <label className="dashboard-field" style={{ marginTop: '0.5rem' }}>
        <input
          type="checkbox"
          checked={filters.compareTo === 'prior_period'}
          onChange={(e) => setFilters({ compareTo: e.target.checked ? 'prior_period' : '' })}
        />
        <span style={{ marginLeft: '0.5rem' }}>Compare to prior period</span>
      </label>

      {orphanedMarketingAccess ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Restore Meta marketing access</h3>
          <p>{metaStatus?.reason.message}</p>
          <div className="dashboard-header__actions-row">
            <Link className="button secondary" to="/dashboards/data-sources?sources=social">
              Restore Meta marketing access
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/accounts">
              Meta accounts
            </Link>
          </div>
        </div>
      ) : null}

      {missingRequiredPermissions.length > 0 ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Reconnect Meta to restore insights access</h3>
          <p>
            The current Meta connection is missing: {missingRequiredPermissions.join(', ')}.
            Reconnect Meta from Data Sources before refreshing or relying on these page metrics.
          </p>
          <div className="dashboard-header__actions-row">
            <button
              className="button secondary"
              type="button"
              onClick={() => void connectOAuthStart({ authType: 'rerequest' })}
            >
              Re-request Meta permissions
            </button>
          </div>
        </div>
      ) : null}

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

      {dashboardStatus === 'loading' ? (
        <div className="dashboard-state">Loading overview…</div>
      ) : null}
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
          {(() => {
            const kpis = overview.kpis.slice(0, 4);
            const allNull = kpis.length > 0 && kpis.every((k) => k.value === null);
            if (kpis.length === 0 || allNull) {
              return (
                <EmptyState
                  icon={<span aria-hidden>0</span>}
                  title="No page data available"
                  message="Try another date range or trigger sync."
                  className="panel"
                  reasonCode="no_page_data"
                />
              );
            }
            return (
              <div
                className="dashboard-grid"
                data-testid="meta-page-kpi-strip"
                style={{ marginBottom: '1rem' }}
              >
                {kpis.map((kpi) => {
                  const availability = overview.metric_availability[kpi.resolved_metric];
                  const availabilityState =
                    availability?.availability_state ??
                    (availability?.supported === false ? 'unsupported' : 'available');
                  const unavailable =
                    availabilityState === 'permission_gated' || availabilityState === 'unsupported';
                  const availabilityHint =
                    availabilityState !== 'available'
                      ? availability?.availability_note || availability?.reason
                      : undefined;
                  return (
                    <KpiTile
                      key={kpi.metric}
                      label={formatMetricLabel(kpi.resolved_metric)}
                      value={kpi.value}
                      format="number"
                      change={kpi.change_pct ?? null}
                      reasonCode={`meta_page_${kpi.resolved_metric}`}
                      isFaded={Boolean(unavailable)}
                      hint={availabilityHint}
                    />
                  );
                })}
              </div>
            );
          })()}

          {timeseriesPoints.length > 0 ? (
            <article className="panel" data-testid="meta-page-trend-panel">
              <h3>{`${formatMetricLabel(selectedMetric)} trend`}</h3>
              <AccessibleTableToggle
                chartAriaLabel={`${formatMetricLabel(selectedMetric)} trend`}
                chart={
                  <TrendLine
                    data={timeseriesPoints.map((p) => ({ date: p.date, value: p.value ?? 0 }))}
                    series={[{ key: 'value', label: formatMetricLabel(selectedMetric) }]}
                    ariaLabel={`${formatMetricLabel(selectedMetric)} trend`}
                    height={260}
                  />
                }
                table={
                  <div className="table-responsive">
                    <table className="dashboard-table">
                      <thead>
                        <tr>
                          <th className="dashboard-table__header-cell">Date</th>
                          <th className="dashboard-table__header-cell">
                            {formatMetricLabel(selectedMetric)}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {timeseriesPoints.map((row) => (
                          <tr key={row.date}>
                            <td className="dashboard-table__cell">{row.date}</td>
                            <td className="dashboard-table__cell">{row.value ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                }
              />
            </article>
          ) : null}

          {timeseriesPoints.length === 0 ? (
            <div className="panel meta-warning-panel" role="status">
              <h3>No trend points available</h3>
              <p>Try another metric or trigger sync.</p>
            </div>
          ) : null}

          {(() => {
            const breakdownEntries = overview.engagement_breakdown?.[selectedMetric] ?? [];
            if (breakdownEntries.length === 0) return null;
            const slices = breakdownEntries.map((entry) => ({
              label: entry.type,
              value: entry.value ?? 0,
            }));
            return (
              <article className="panel" data-testid="meta-page-engagement-panel">
                <h3>Engagement Breakdown</h3>
                <PieComposition
                  data={slices}
                  ariaLabel={`${formatMetricLabel(selectedMetric)} engagement breakdown`}
                  height={260}
                />
              </article>
            );
          })()}
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
