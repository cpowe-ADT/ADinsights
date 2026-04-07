import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import { loadSocialConnectionStatus, type SocialPlatformStatusRecord } from '../lib/airbyte';
import { startMetaOAuth } from '../lib/metaPageInsights';

const MetaConnectionStatusPage = () => {
  const navigate = useNavigate();
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
  const metaPermissionGap = useMemo(
    () => rows.find((row) => row.platform === 'meta' && row.reason.code === 'page_insights_permissions_missing'),
    [rows],
  );
  const orphanedMarketingAccess = useMemo(
    () => rows.find((row) => row.platform === 'meta' && row.reason.code === 'orphaned_marketing_access'),
    [rows],
  );
  const metaReportingReadiness = useMemo(
    () => rows.find((row) => row.platform === 'meta')?.reporting_readiness ?? null,
    [rows],
  );

  const handleReconnectMeta = async () => {
    const payload = await startMetaOAuth('rerequest');
    window.location.assign(payload.authorize_url);
  };

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Connection status</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/data-sources?sources=social">
            Connect socials
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/pages">
            Facebook pages
          </Link>
          {orphanedMarketingAccess ? (
            <button
              type="button"
              className="button secondary"
              onClick={() => navigate('/dashboards/data-sources?sources=social')}
            >
              Restore Meta marketing access
            </button>
          ) : null}
          {metaPermissionGap ? (
            <button type="button" className="button secondary" onClick={() => void handleReconnectMeta()}>
              Reconnect Meta
            </button>
          ) : null}
          <button type="button" className="button secondary" onClick={() => void reload()}>
            Refresh
          </button>
        </div>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <p className="status-message muted" style={{ margin: 0 }}>
          Connection status tracks Meta auth/setup, direct sync, and live warehouse readiness as
          separate stages so the app can show the exact blocker instead of a generic failure.
        </p>
      </div>

      <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
        <article className="panel">
          <h3>Platforms tracked</h3>
          <strong>{rows.length}</strong>
        </article>
        <article className="panel">
          <h3>Has active sync</h3>
          <strong>{hasActive ? 'Yes' : 'No'}</strong>
        </article>
        <article className="panel">
          <h3>Reporting stage</h3>
          <strong>{metaReportingReadiness?.stage ?? 'Not evaluated'}</strong>
          <p className="muted" style={{ marginBottom: 0 }}>
            {metaReportingReadiness?.message ?? 'Connect Meta to evaluate reporting readiness.'}
          </p>
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
          message="Connect socials from Data Sources to populate Meta and Instagram status."
          actionLabel="Connect socials"
          onAction={() => navigate('/dashboards/data-sources?sources=social')}
          secondaryActionLabel="Facebook pages"
          onSecondaryAction={() => navigate('/dashboards/meta/pages')}
          className="panel"
        />
      ) : null}
      {status === 'loaded' && rows.length > 0 ? (
        <>
          {orphanedMarketingAccess ? (
            <div className="panel meta-warning-panel" role="status">
              <h3>Restore Meta marketing access</h3>
              <p>{orphanedMarketingAccess.reason.message}</p>
              <div className="dashboard-header__actions-row">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => navigate('/dashboards/data-sources?sources=social')}
                >
                  Restore Meta marketing access
                </button>
                <Link className="button tertiary" to="/">
                  Home
                </Link>
              </div>
            </div>
          ) : null}
          {metaPermissionGap ? (
            <div className="panel meta-warning-panel" role="status">
              <h3>Reconnect Meta to restore Page Insights</h3>
              <p>{metaPermissionGap.reason.message}</p>
              <div className="dashboard-header__actions-row">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => void handleReconnectMeta()}
                >
                  Re-request Meta permissions
                </button>
              </div>
            </div>
          ) : null}
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
        </>
      ) : null}
    </section>
  );
};

export default MetaConnectionStatusPage;
