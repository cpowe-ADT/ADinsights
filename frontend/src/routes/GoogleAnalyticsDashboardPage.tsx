import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import StatCard from '../components/ui/StatCard';
import { formatCurrency, formatNumber, formatPercent } from '../lib/formatNumber';
import {
  fetchGoogleAnalyticsWebRows,
  type GoogleAnalyticsWebResponse,
  type GoogleAnalyticsWebRow,
} from '../lib/webAnalytics';

type LoadState = 'loading' | 'loaded' | 'error';

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
  const totals = useMemo(() => {
    return rows.reduce(
      (accumulator, row) => {
        accumulator.sessions += Number(row.sessions || 0);
        accumulator.engagedSessions += Number(row.engaged_sessions || 0);
        accumulator.conversions += Number(row.conversions || 0);
        accumulator.purchaseRevenue += Number(row.purchase_revenue || 0);
        return accumulator;
      },
      {
        sessions: 0,
        engagedSessions: 0,
        conversions: 0,
        purchaseRevenue: 0,
      },
    );
  }, [rows]);

  const topChannel = useMemo(() => {
    const channelTotals = new Map<string, number>();
    rows.forEach((row) => {
      const channel = row.channel_group?.trim() || 'Unassigned';
      channelTotals.set(channel, (channelTotals.get(channel) ?? 0) + Number(row.sessions || 0));
    });
    let topLabel = '—';
    let topValue = 0;
    channelTotals.forEach((value, key) => {
      if (value > topValue) {
        topValue = value;
        topLabel = key;
      }
    });
    return topLabel;
  }, [rows]);

  const latestRow = rows[0] ?? null;

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

      <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
        <StatCard label="Sessions" value={formatNumber(totals.sessions)} />
        <StatCard label="Conversions" value={formatNumber(totals.conversions)} />
        <StatCard label="Revenue" value={formatCurrency(totals.purchaseRevenue)} />
        <StatCard label="Top channel" value={topChannel} />
      </div>

      {latestRow ? (
        <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
          <article className="panel">
            <h3>Latest row</h3>
            <p className="status-message muted">{latestRow.date_day}</p>
            <p>{latestRow.campaign_name || 'No campaign name'}</p>
          </article>
          <article className="panel">
            <h3>Engagement rate</h3>
            <p>{formatPercent(latestRow.engagement_rate)}</p>
          </article>
          <article className="panel">
            <h3>Conversion rate</h3>
            <p>{formatPercent(latestRow.conversion_rate)}</p>
          </article>
        </div>
      ) : null}

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
          className="panel"
        />
      ) : null}

      {status === 'loaded' && payload?.status === 'unavailable' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="GA4 warehouse feed unavailable"
          message={payload.detail ?? 'The backend reported this source as unavailable.'}
          actionLabel="Open Data Sources"
          actionVariant="secondary"
          onAction={() => {
            window.location.assign('/dashboards/data-sources');
          }}
          className="panel"
        />
      ) : null}

      {status === 'loaded' && payload?.status === 'ok' && rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No GA4 rows available"
          message="Connect a GA4 property from Data Sources or widen the selected date range."
          actionLabel="Open Data Sources"
          actionVariant="secondary"
          onAction={() => {
            window.location.assign('/dashboards/data-sources');
          }}
          className="panel"
        />
      ) : null}

      {status === 'loaded' && payload?.status === 'ok' && rows.length > 0 ? (
        <div className="panel">
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Date</th>
                  <th className="dashboard-table__header-cell">Channel</th>
                  <th className="dashboard-table__header-cell">Campaign</th>
                  <th className="dashboard-table__header-cell">Sessions</th>
                  <th className="dashboard-table__header-cell">Engaged</th>
                  <th className="dashboard-table__header-cell">Conversions</th>
                  <th className="dashboard-table__header-cell">Revenue</th>
                  <th className="dashboard-table__header-cell">Location</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: GoogleAnalyticsWebRow) => (
                  <tr key={`${row.date_day}-${row.property_id}-${row.channel_group}-${row.campaign_name}`}>
                    <td className="dashboard-table__cell">{row.date_day}</td>
                    <td className="dashboard-table__cell">{row.channel_group || '—'}</td>
                    <td className="dashboard-table__cell">{row.campaign_name || '—'}</td>
                    <td className="dashboard-table__cell">{formatNumber(row.sessions)}</td>
                    <td className="dashboard-table__cell">{formatNumber(row.engaged_sessions)}</td>
                    <td className="dashboard-table__cell">{formatNumber(row.conversions)}</td>
                    <td className="dashboard-table__cell">{formatCurrency(row.purchase_revenue)}</td>
                    <td className="dashboard-table__cell">
                      {[row.city, row.country].filter(Boolean).join(', ') || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default GoogleAnalyticsDashboardPage;
