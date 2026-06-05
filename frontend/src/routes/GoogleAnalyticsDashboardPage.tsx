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
import { formatNumber } from '../lib/formatNumber';
import {
  fetchGoogleAnalyticsWebRows,
  type GoogleAnalyticsWebResponse,
  type GoogleAnalyticsWebRow,
} from '../lib/webAnalytics';
import {
  aggregateGa4ByChannel,
  aggregateGa4Totals,
  aggregateGa4TrendByDay,
  type Ga4ChannelDatum,
} from '../lib/webAnalyticsAggregates';

/**
 * R3 CRITICAL: This page MUST NOT import `useDashboardStore` and MUST NOT
 * call `/api/metrics/combined/`. It uses its own dedicated endpoint
 * (`/analytics/web/ga4/`) via `fetchGoogleAnalyticsWebRows`.
 *
 * GA4 payload availability note (S4 architect §3): rows DO NOT carry
 * `users`, `bounce_rate`, or `avg_session_duration`. We substitute the KPI
 * strip with: Sessions / Conversions / Revenue / Engagement rate — the
 * present fields confirmed by the architect audit.
 */

type LoadState = 'loading' | 'loaded' | 'error';

const PIE_PALETTE = [
  '#6366f1',
  '#22c55e',
  '#f59e0b',
  '#ec4899',
  '#14b8a6',
  '#a855f7',
  '#94a3b8',
] as const;

function defaultDateRange(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 24 * 60 * 60 * 1000);
  const toIsoDate = (value: Date) => value.toISOString().slice(0, 10);
  return { startDate: toIsoDate(start), endDate: toIsoDate(end) };
}

const GoogleAnalyticsDashboardPage = () => {
  const defaults = useMemo(() => defaultDateRange(), []);
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const [status, setStatus] = useState<LoadState>('loading');
  const [payload, setPayload] = useState<GoogleAnalyticsWebResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const response = await fetchGoogleAnalyticsWebRows({
        start_date: startDate,
        end_date: endDate,
      });
      setPayload(response);
      setStatus('loaded');
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : 'Unable to load GA4 dashboard data.');
      setStatus('error');
    }
  }, [startDate, endDate]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const rows = useMemo(() => payload?.rows ?? [], [payload]);
  const totals = useMemo(() => aggregateGa4Totals(rows), [rows]);
  const trendData = useMemo(() => aggregateGa4TrendByDay(rows), [rows]);
  const channelRows = useMemo(() => aggregateGa4ByChannel(rows), [rows]);

  const pieData = useMemo(() => {
    if (channelRows.length === 0) return [];
    const sorted = [...channelRows].sort((a, b) => b.sessions - a.sessions);
    const topSix = sorted.slice(0, 6);
    const other = sorted.slice(6);
    const slices: Array<{ label: string; value: number; color: string }> = topSix.map(
      (row, idx) => ({
        label: row.channel,
        value: row.sessions,
        color: PIE_PALETTE[idx % PIE_PALETTE.length],
      }),
    );
    if (other.length > 0) {
      slices.push({
        label: 'Other',
        value: other.reduce((sum, row) => sum + row.sessions, 0),
        color: PIE_PALETTE[6],
      });
    }
    return slices;
  }, [channelRows]);

  const channelTableColumns = useMemo(
    () => [
      { accessorKey: 'channel', header: 'Channel' },
      {
        accessorKey: 'sessions',
        header: 'Sessions',
        cell: ({ row }: { row: { original: Ga4ChannelDatum } }) =>
          formatNumber(row.original.sessions),
      },
      {
        accessorKey: 'conversions',
        header: 'Conversions',
        cell: ({ row }: { row: { original: Ga4ChannelDatum } }) =>
          formatNumber(row.original.conversions),
      },
      {
        accessorKey: 'purchaseRevenue',
        header: 'Revenue',
        cell: ({ row }: { row: { original: Ga4ChannelDatum } }) =>
          row.original.purchaseRevenue.toLocaleString(undefined, {
            style: 'currency',
            currency: 'USD',
          }),
      },
      {
        accessorKey: 'engagementRate',
        header: 'Engagement rate',
        cell: ({ row }: { row: { original: Ga4ChannelDatum } }) =>
          `${(row.original.engagementRate * 100).toFixed(1)}%`,
      },
    ],
    [],
  );

  const isOk = status === 'loaded' && payload?.status === 'ok';
  const isUnavailable = status === 'loaded' && payload?.status === 'unavailable';
  const isEmpty = isOk && rows.length === 0;
  const isReady = isOk && rows.length > 0;

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Web analytics</p>
        <h1 className="dashboardHeading">Google Analytics 4</h1>
        <p className="status-message muted">
          Review tenant-scoped GA4 sessions, engagement, conversions, and revenue from the warehouse
          pilot feed.
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
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
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

      {/* Block 1 — KPI strip. Substitutes Sessions / Conversions / Revenue / Engagement
          rate because the GA4 feed does not expose Users, Bounce rate, or Avg session duration
          (per architect §3 availability audit). */}
      <div
        className="dashboard-grid"
        role="group"
        aria-label="GA4 KPIs"
        style={{ marginBottom: '1rem' }}
      >
        <KpiTile
          label="Sessions"
          value={isReady ? totals.sessions : null}
          format="number"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Conversions"
          value={isReady ? totals.conversions : null}
          format="number"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Revenue"
          value={isReady ? totals.purchaseRevenue : null}
          format="currency"
          currency="USD"
          isLoading={status === 'loading'}
        />
        <KpiTile
          label="Engagement rate"
          value={isReady ? totals.engagementRate : null}
          format="percent"
          isLoading={status === 'loading'}
        />
      </div>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading GA4 metrics…</div>
      ) : null}

      {status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load GA4 data"
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
          title="GA4 warehouse feed unavailable"
          message={payload?.detail ?? 'The backend reported this source as unavailable.'}
          actionLabel="Open Data Sources"
          actionVariant="secondary"
          onAction={() => {
            window.location.assign('/dashboards/data-sources');
          }}
          reasonCode="no_ga4_property_selected"
          className="panel"
        />
      ) : null}

      {isEmpty ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No GA4 rows available"
          message="Connect a GA4 property from Data Sources or widen the selected date range."
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
          {/* Block 2 — Sessions/day trend */}
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <header className="panel-header">
              <h2>Sessions over time</h2>
              <p className="muted">Daily session totals aggregated from GA4 rows.</p>
            </header>
            <AccessibleTableToggle
              chartAriaLabel="Sessions per day"
              chart={
                <TrendLine
                  ariaLabel="Sessions per day"
                  data={trendData}
                  series={[{ key: 'sessions', label: 'Sessions', color: '#6366f1' }]}
                  yFormat="number"
                  emptyReasonCode="no_data_for_range"
                />
              }
              table={
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Sessions</th>
                      <th>Conversions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trendData.map((row) => (
                      <tr key={row.date}>
                        <td>{row.date}</td>
                        <td>{formatNumber(row.sessions)}</td>
                        <td>{formatNumber(row.conversions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              }
            />
          </section>

          {/* Block 3 — Channel composition */}
          <section className="panel" style={{ marginBottom: '1rem' }}>
            <header className="panel-header">
              <h2>Sessions by channel</h2>
              <p className="muted">Top 6 channel groups plus &quot;Other&quot;.</p>
            </header>
            <AccessibleTableToggle
              chartAriaLabel="Sessions by channel"
              chart={
                <PieComposition
                  ariaLabel="Sessions by channel group"
                  data={pieData}
                  yFormat="number"
                  emptyReasonCode="no_data_for_range"
                />
              }
              table={
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>Sessions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pieData.map((slice) => (
                      <tr key={slice.label}>
                        <td>{slice.label}</td>
                        <td>{formatNumber(slice.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              }
            />
          </section>

          {/* Block 4 — Drill-down VizDataTable */}
          <section className="panel">
            <VizDataTable
              ariaLabel="GA4 channel breakdown"
              title="Channel breakdown"
              csvFilename="ga4-channel-breakdown.csv"
              columns={channelTableColumns as never}
              data={channelRows}
            />
          </section>

          {/* Legacy raw-row table preserved for historical consumers */}
          <div className="panel" style={{ marginTop: '1rem' }}>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    <th className="dashboard-table__header-cell">Date</th>
                    <th className="dashboard-table__header-cell">Channel</th>
                    <th className="dashboard-table__header-cell">Campaign</th>
                    <th className="dashboard-table__header-cell">Sessions</th>
                    <th className="dashboard-table__header-cell">Conversions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: GoogleAnalyticsWebRow) => (
                    <tr
                      key={`${row.date_day}-${row.property_id}-${row.channel_group}-${row.campaign_name}`}
                    >
                      <td className="dashboard-table__cell">{row.date_day}</td>
                      <td className="dashboard-table__cell">{row.channel_group || '—'}</td>
                      <td className="dashboard-table__cell">{row.campaign_name || '—'}</td>
                      <td className="dashboard-table__cell">{formatNumber(row.sessions)}</td>
                      <td className="dashboard-table__cell">{formatNumber(row.conversions)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
};

export default GoogleAnalyticsDashboardPage;
