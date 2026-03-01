import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import { loadSocialConnectionStatus, type SocialPlatformStatusRecord } from '../lib/airbyte';

const MetaConnectionStatusPage = () => {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [rows, setRows] = useState<SocialPlatformStatusRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    setStatus('loading');
    setError(null);
    try {
      const payload = await loadSocialConnectionStatus();
      setRows(
        payload.platforms.filter((row) => row.platform === 'meta' || row.platform === 'instagram'),
      );
      setStatus('loaded');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load Meta connection status.';
      setError(message);
      setStatus('error');
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const hasActive = useMemo(() => rows.some((row) => row.status === 'active'), [rows]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Connection status</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/data-sources?sources=social">
            Open Data Sources
          </Link>
          <button type="button" className="button secondary" onClick={() => void reload()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
        <article className="panel">
          <h3>Platforms tracked</h3>
          <strong>{rows.length}</strong>
        </article>
        <article className="panel">
          <h3>Has active sync</h3>
          <strong>{hasActive ? 'Yes' : 'No'}</strong>
        </article>
      </div>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading status...</div>
      ) : null}
      {status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load connection status"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => void reload()}
          className="panel"
        />
      ) : null}
      {status === 'loaded' && rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No Meta status yet"
          message="Connect Meta from Data Sources to populate status."
          className="panel"
        />
      ) : null}
      {status === 'loaded' && rows.length > 0 ? (
        <div className="panel">
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Platform</th>
                  <th className="dashboard-table__header-cell">Status</th>
                  <th className="dashboard-table__header-cell">Reason</th>
                  <th className="dashboard-table__header-cell">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.platform}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">{row.display_name}</td>
                    <td className="dashboard-table__cell">{row.status}</td>
                    <td className="dashboard-table__cell">{row.reason.message}</td>
                    <td className="dashboard-table__cell">{row.actions.join(', ') || '—'}</td>
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

export default MetaConnectionStatusPage;
