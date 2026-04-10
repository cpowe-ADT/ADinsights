import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import Breadcrumbs from '../components/Breadcrumbs';
import EmptyState from '../components/EmptyState';
import { loadSocialConnectionStatus, type SocialPlatformStatusRecord } from '../lib/airbyte';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const MetaPagesListPage = () => {
  const navigate = useNavigate();
  const {
    pagesStatus,
    pages,
    missingRequiredPermissions,
    error,
    loadPages,
    connectOAuthStart,
    selectDefaultPage,
  } = useMetaPageInsightsStore((state) => ({
    pagesStatus: state.pagesStatus,
    pages: state.pages,
    missingRequiredPermissions: state.missingRequiredPermissions,
    error: state.error,
    loadPages: state.loadPages,
    connectOAuthStart: state.connectOAuthStart,
    selectDefaultPage: state.selectDefaultPage,
  }));
  const [metaStatus, setMetaStatus] = useState<SocialPlatformStatusRecord | null>(null);

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

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

  const requiresPermissionReconnect = missingRequiredPermissions.length > 0;
  const orphanedMarketingAccess = useMemo(
    () => metaStatus?.reason.code === 'orphaned_marketing_access',
    [metaStatus?.reason.code],
  );

  return (
    <section className="dashboardPage">
      <Breadcrumbs
        items={[
          { label: 'Dashboards', to: '/dashboards' },
          { label: 'Facebook Pages' },
        ]}
      />
      <header className="dashboardPageHeader">
        <h1 className="dashboardHeading">Facebook Pages</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/data-sources?sources=social">
            Connect socials
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/status">
            Connection status
          </Link>
          {orphanedMarketingAccess ? (
            <button
              className="button secondary"
              type="button"
              onClick={() => navigate('/dashboards/data-sources?sources=social')}
            >
              Restore Meta marketing access
            </button>
          ) : null}
          <button
            className="button secondary"
            type="button"
            onClick={() =>
              void connectOAuthStart(
                requiresPermissionReconnect ? { authType: 'rerequest' } : undefined,
              )
            }
          >
            {requiresPermissionReconnect ? 'Reconnect Meta' : 'Connect for Page Insights'}
          </button>
        </div>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <p className="status-message muted" style={{ margin: 0 }}>
          This screen lists Facebook Pages only. Meta ad accounts such as JDIC and SLB show up
          under <Link to="/dashboards/meta/accounts">Meta accounts</Link>, not here.
        </p>
      </div>

      {pagesStatus === 'loading' ? <div className="dashboard-state">Loading pages…</div> : null}
      {pagesStatus === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load Facebook pages"
          message={error ?? 'Try again.'}
          actionLabel="Retry"
          onAction={() => void loadPages()}
          className="panel"
        />
      ) : null}

      {pagesStatus === 'loaded' && pages.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No Pages available"
          message={
            orphanedMarketingAccess
              ? metaStatus?.reason.message ??
                'Restore Meta marketing access to reconnect ad accounts and reporting.'
              : 'Connect Meta and ensure the user has insights capability (ANALYZE task or admin page role) on at least one Page. Ad accounts are managed separately under Meta accounts.'
          }
          actionLabel={orphanedMarketingAccess ? 'Restore Meta marketing access' : 'Connect socials'}
          onAction={() => navigate('/dashboards/data-sources?sources=social')}
          secondaryActionLabel="Home"
          onSecondaryAction={() => navigate('/')}
          className="panel"
        />
      ) : null}

      {orphanedMarketingAccess ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Restore Meta marketing access</h3>
          <p>{metaStatus?.reason.message}</p>
          <div className="dashboard-header__actions-row">
            <button
              className="button secondary"
              type="button"
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

      {missingRequiredPermissions.length > 0 ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Reconnect Meta to restore Page Insights</h3>
          <p>
            The current Meta connection is missing: {missingRequiredPermissions.join(', ')}. Reconnect
            Meta from Data Sources so page reporting and refresh actions can run again.
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

      {pages.length > 0 ? (
        <article className="panel">
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Page</th>
                  <th className="dashboard-table__header-cell">Category</th>
                  <th className="dashboard-table__header-cell">Analyze</th>
                  <th className="dashboard-table__header-cell">Default</th>
                  <th className="dashboard-table__header-cell">Last synced</th>
                  <th className="dashboard-table__header-cell">Action</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((page) => (
                  <tr key={page.id} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{page.name}</td>
                    <td className="dashboard-table__cell">{page.category || '—'}</td>
                    <td className="dashboard-table__cell">{page.can_analyze ? 'Yes' : 'No'}</td>
                    <td className="dashboard-table__cell">{page.is_default ? 'Yes' : 'No'}</td>
                    <td className="dashboard-table__cell">{page.last_synced_at ? page.last_synced_at.slice(0, 19) : '—'}</td>
                    <td className="dashboard-table__cell">
                      <button
                        type="button"
                        className="button tertiary"
                        onClick={() => {
                          void selectDefaultPage(page.page_id).catch(() => undefined);
                        }}
                      >
                        Set default
                      </button>
                      <button
                        type="button"
                        className="button tertiary"
                        disabled={!page.can_analyze}
                        onClick={() => navigate(`/dashboards/meta/pages/${page.page_id}/overview`)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}
    </section>
  );
};

export default MetaPagesListPage;
