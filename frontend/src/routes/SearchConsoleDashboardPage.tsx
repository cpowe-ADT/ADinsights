import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import StatCard from '../components/ui/StatCard';
import { formatNumber, formatPercent } from '../lib/formatNumber';
import {
  fetchSearchConsoleWebRows,
  type SearchConsoleWebResponse,
  type SearchConsoleWebRow,
} from '../lib/webAnalytics';

type LoadState = 'loading' | 'loaded' | 'error';

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

  const rows = useMemo(() => {
    const raw = payload?.rows ?? [];
    return [...raw].sort((a, b) => b.clicks - a.clicks);
  }, [payload]);

  const totals = useMemo(() => {
    return rows.reduce(
      (accumulator, row) => {
        accumulator.clicks += Number(row.clicks || 0);
        accumulator.impressions += Number(row.impressions || 0);
        accumulator.ctrSum += Number(row.ctr || 0);
        accumulator.positionSum += Number(row.position || 0);
        accumulator.count += 1;
        return accumulator;
      },
      {
        clicks: 0,
        impressions: 0,
        ctrSum: 0,
        positionSum: 0,
        count: 0,
      },
    );
  }, [rows]);

  const avgCtr = totals.count > 0 ? totals.ctrSum / totals.count : 0;
  const avgPosition = totals.count > 0 ? totals.positionSum / totals.count : 0;

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

      <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
        <StatCard label="Total Clicks" value={formatNumber(totals.clicks)} />
        <StatCard label="Total Impressions" value={formatNumber(totals.impressions)} />
        <StatCard label="Average CTR" value={formatPercent(avgCtr)} />
        <StatCard label="Average Position" value={avgPosition.toFixed(1)} />
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
          className="panel"
        />
      ) : null}

      {status === 'loaded' && payload?.status === 'unavailable' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Search Console feed unavailable"
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
          title="No Search Console rows available"
          message="Connect a Search Console property from Data Sources or widen the selected date range."
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
                  <th className="dashboard-table__header-cell">Query</th>
                  <th className="dashboard-table__header-cell">Page</th>
                  <th className="dashboard-table__header-cell">Device</th>
                  <th className="dashboard-table__header-cell">Country</th>
                  <th className="dashboard-table__header-cell">Clicks</th>
                  <th className="dashboard-table__header-cell">Impressions</th>
                  <th className="dashboard-table__header-cell">CTR</th>
                  <th className="dashboard-table__header-cell">Position</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: SearchConsoleWebRow) => (
                  <tr key={`${row.date_day}-${row.query}-${row.page}-${row.device}-${row.country}`}>
                    <td className="dashboard-table__cell">{row.date_day}</td>
                    <td className="dashboard-table__cell">{row.query || '—'}</td>
                    <td className="dashboard-table__cell">{row.page || '—'}</td>
                    <td className="dashboard-table__cell">{row.device || '—'}</td>
                    <td className="dashboard-table__cell">{row.country || '—'}</td>
                    <td className="dashboard-table__cell">{formatNumber(row.clicks)}</td>
                    <td className="dashboard-table__cell">{formatNumber(row.impressions)}</td>
                    <td className="dashboard-table__cell">{formatPercent(row.ctr)}</td>
                    <td className="dashboard-table__cell">{row.position.toFixed(1)}</td>
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

export default SearchConsoleDashboardPage;
