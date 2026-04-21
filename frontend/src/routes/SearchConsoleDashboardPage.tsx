import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  AccessibleTableToggle,
  EmptyState,
  KpiTile,
  PieComposition,
  TrendLine,
  VizDataTable,
} from '../components/viz';
import { formatNumber, formatPercent } from '../lib/formatNumber';
import {
  fetchSearchConsoleWebRows,
  type SearchConsoleWebResponse,
} from '../lib/webAnalytics';
import {
  aggregateSearchConsoleByDevice,
  aggregateSearchConsoleTopQueries,
  aggregateSearchConsoleTotals,
  aggregateSearchConsoleTrendByDay,
  type SearchConsoleQueryRow,
} from '../lib/webAnalyticsAggregates';

/**
 * R3 CRITICAL: This page MUST NOT import `useDashboardStore` and MUST NOT
 * call `/api/metrics/combined/`. It uses its own dedicated endpoint
 * (`/analytics/web/search-console/`) via `fetchSearchConsoleWebRows`.
 */

type LoadState = 'loading' | 'loaded' | 'error';

const DEVICE_PALETTE: Record<string, string> = {
  mobile: '#6366f1',
  desktop: '#22c55e',
  tablet: '#f59e0b',
  unknown: '#94a3b8',
};

function defaultDateRange(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 24 * 60 * 60 * 1000);
  const toIsoDate = (value: Date) => value.toISOString().slice(0, 10);
  return { startDate: toIsoDate(start), endDate: toIsoDate(end) };
}

const SearchConsoleDashboardPage = () => {
  const defaults = useMemo(() => defaultDateRange(), []);
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const [status, setStatus] = useState<LoadState>('loading');
  const [payload, setPayload] = useState<SearchConsoleWebResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const response = await fetchSearchConsoleWebRows({
        start_date: startDate,
        end_date: endDate,
      });
      setPayload(response);
      setStatus('loaded');
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : 'Unable to load Search Console data.');
      setStatus('error');
    }
  }, [startDate, endDate]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const rawRows = useMemo(() => payload?.rows ?? [], [payload]);

  const totals = useMemo(() => aggregateSearchConsoleTotals(rawRows), [rawRows]);
  const trendData = useMemo(() => aggregateSearchConsoleTrendByDay(rawRows), [rawRows]);
  const deviceRows = useMemo(() => aggregateSearchConsoleByDevice(rawRows), [rawRows]);
  const topQueries = useMemo(
    () => aggregateSearchConsoleTopQueries(rawRows, 50),
    [rawRows],
  );

  const pieData = useMemo(
    () =>
      deviceRows.map((row) => ({
        label: row.device.charAt(0).toUpperCase() + row.device.slice(1),
        value: row.clicks,
        color: DEVICE_PALETTE[row.device.toLowerCase()] ?? '#94a3b8',
      })),
    [deviceRows],
  );

  const queryTableColumns = useMemo(
    () => [
      { accessorKey: 'query', header: 'Query' },
      {
        accessorKey: 'clicks',
        header: 'Clicks',
        cell: ({ row }: { row: { original: SearchConsoleQueryRow } }) =>
          formatNumber(row.original.clicks),
      },
      {
        accessorKey: 'impressions',
        header: 'Impressions',
        cell: ({ row }: { row: { original: SearchConsoleQueryRow } }) =>
          formatNumber(row.original.impressions),
      },
      {
        accessorKey: 'ctr',
        header: 'CTR',
        cell: ({ row }: { row: { original: SearchConsoleQueryRow } }) =>
          formatPercent(row.original.ctr),
      },
      {
        accessorKey: 'avgPosition',
        header: 'Avg position',
        cell: ({ row }: { row: { original: SearchConsoleQueryRow } }) =>
          row.original.avgPosition.toFixed(1),
      },
    ],
    [],
  );

  const isOk = status === 'loaded' && payload?.status === 'ok';
  const isUnavailable = status === 'loaded' && payload?.status === 'unavailable';
  const isEmpty = isOk && rawRows.length === 0;
  const isReady = isOk && rawRows.length > 0;

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Web analytics</p>
        <h1 className="dashboardHeading">Search Console</h1>
        <p className="status-message muted">
          Review tenant-scoped Search Console clicks, impressions, CTR, and position from the
          warehouse pilot feed.
        </p>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/data-sources">
            Open Data Sources
          </Link>
          <button type="button" className="button secondary" onClick={() => void loadRows()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="data-sources-controls" style={{ marginBottom: '1rem' }}>
        <label className="dashboard-field">
          <span className="dashboard-field__label">Start date</span>
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label className="dashboard-field">
          <span className="dashboard-field__label">End date</span>
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
        <div className="data-sources-actions">
          <button type="button" className="button secondary" onClick={() => void loadRows()}>
            Apply range
          </button>
        </div>
      </div>

      {/* Block 1 — KPI strip */}
      <div className="dashboard-grid" role="group" aria-label="Search Console KPIs" style={{ marginBottom: '1rem' }}>
        <KpiTile
          label="Total Clicks"
          value={isReady ? totals.clicks : null}
          format="number"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Total Impressions"
          value={isReady ? totals.impressions : null}
          format="number"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Average CTR"
          value={isReady ? totals.ctr : null}
          format="percent"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Average Position"
          value={isReady ? totals.avgPosition : null}
          format="number"
          hint="Lower is better"
          isLoading={status === 'loading'}
        />
      </div>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading Search Console metrics…</div>
      ) : null}

      {status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load Search Console data"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          actionVariant="secondary"
          onAction={() => void loadRows()}
          reasonCode="error"
          className="panel"
        />
      ) : null}

      {isUnavailable ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Search Console feed unavailable"
          message={payload?.detail ?? 'The backend reported this source as unavailable.'}
          actionLabel="Open Data Sources"
          actionVariant="secondary"
          onAction={() => {
            window.location.assign('/dashboards/data-sources');
          }}
          reasonCode="no_search_console_site_selected"
          className="panel"
        />
      ) : null}

      {isEmpty ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No Search Console rows available"
          message="Connect a Search Console property from Data Sources or widen the selected date range."
          actionLabel="Open Data Sources"
          actionVariant="secondary"
          onAction={() => {
            window.location.assign('/dashboards/data-sources');
          }}
          reasonCode="no_data_for_range"
          className="panel"
        />
      ) : null}

      {isReady ? (
        <>
          {/* Block 2 — Dual-axis Clicks + Impressions trend */}
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <header className="panel-header">
              <h2>Clicks &amp; impressions over time</h2>
              <p className="muted">Dual axis: clicks (left), impressions (right).</p>
            </header>
            <AccessibleTableToggle
              chartAriaLabel="Clicks and impressions per day"
              chart={
                <TrendLine
                  ariaLabel="Clicks (left axis) and impressions (right axis) per day"
                  data={trendData}
                  series={[
                    { key: 'clicks', label: 'Clicks', color: '#6366f1', yAxis: 'left' },
                    { key: 'impressions', label: 'Impressions', color: '#22c55e', yAxis: 'right' },
                  ]}
                  yFormat="number"
                  rightYFormat="number"
                  emptyReasonCode="no_data_for_range"
                />
              }
              table={
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Clicks</th>
                      <th>Impressions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trendData.map((row) => (
                      <tr key={row.date}>
                        <td>{row.date}</td>
                        <td>{formatNumber(row.clicks)}</td>
                        <td>{formatNumber(row.impressions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              }
            />
          </section>

          {/* Block 3 — Device composition */}
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <header className="panel-header">
              <h2>Clicks by device</h2>
            </header>
            <AccessibleTableToggle
              chartAriaLabel="Clicks by device"
              chart={
                <PieComposition
                  ariaLabel="Clicks by device"
                  data={pieData}
                  yFormat="number"
                  emptyReasonCode="no_data_for_range"
                />
              }
              table={
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>Device</th>
                      <th>Clicks</th>
                      <th>Impressions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deviceRows.map((row) => (
                      <tr key={row.device}>
                        <td>{row.device}</td>
                        <td>{formatNumber(row.clicks)}</td>
                        <td>{formatNumber(row.impressions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              }
            />
          </section>

          {/* Block 4 — Top 50 queries drill-down */}
          <section className="panel">
            <VizDataTable
              ariaLabel="Top search queries"
              title="Top queries (top 50 by clicks)"
              csvFilename="search-console-top-queries.csv"
              columns={queryTableColumns as never}
              data={topQueries}
            />
          </section>
        </>
      ) : null}
    </section>
  );
};

export default SearchConsoleDashboardPage;
