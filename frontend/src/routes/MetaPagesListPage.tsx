import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';
import '../styles/dashboard.css';

const MetaPagesListPage = () => {
  const navigate = useNavigate();
  const {
    pagesStatus,
    pages,
    error,
    loadPages,
    connectOAuthStart,
    selectDefaultPage,
  } = useMetaPageInsightsStore((state) => ({
    pagesStatus: state.pagesStatus,
    pages: state.pages,
    error: state.error,
    loadPages: state.loadPages,
    connectOAuthStart: state.connectOAuthStart,
    selectDefaultPage: state.selectDefaultPage,
  }));

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Dashboards</p>
        <h1 className="dashboardHeading">Facebook Pages</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/integrations/meta">
            Manage connection
          </Link>
          <button className="button secondary" type="button" onClick={() => void connectOAuthStart()}>
            Connect for Page Insights
          </button>
        </div>
      </header>

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
          message="Connect Meta and ensure the user has insights capability (ANALYZE task or admin page role) on at least one Page."
          actionLabel="Connect now"
          onAction={() => void connectOAuthStart()}
          className="panel"
        />
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
