import { useEffect, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import useMetaPageInsightsStore from '../state/useMetaPageInsightsStore';

const MetaIntegrationPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const {
    pagesStatus,
    oauthStatus,
    pages,
    error,
    missingRequiredPermissions,
    selectedPageId,
    connectOAuthStart,
    connectOAuthCallback,
    loadPages,
    selectDefaultPage,
  } = useMetaPageInsightsStore((state) => ({
    pagesStatus: state.pagesStatus,
    oauthStatus: state.oauthStatus,
    pages: state.pages,
    error: state.error,
    missingRequiredPermissions: state.missingRequiredPermissions,
    selectedPageId: state.selectedPageId,
    connectOAuthStart: state.connectOAuthStart,
    connectOAuthCallback: state.connectOAuthCallback,
    loadPages: state.loadPages,
    selectDefaultPage: state.selectDefaultPage,
  }));

  const oauthCode = searchParams.get('code') ?? '';
  const oauthState = searchParams.get('state') ?? '';

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  useEffect(() => {
    if (!oauthCode || !oauthState) {
      return;
    }
    void connectOAuthCallback(oauthCode, oauthState);
  }, [oauthCode, oauthState, connectOAuthCallback]);

  const selectedPage = useMemo(
    () => pages.find((page) => page.page_id === selectedPageId) ?? pages.find((page) => page.is_default),
    [pages, selectedPageId],
  );

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Integrations</p>
        <h1 className="dashboardHeading">Meta</h1>
        <div className="dashboard-header__actions-row">
          <button type="button" className="button secondary" onClick={() => void connectOAuthStart()}>
            Connect for Page Insights
          </button>
          {selectedPage ? (
            <Link className="button tertiary" to={`/dashboards/meta/pages/${selectedPage.page_id}/overview`}>
              Open dashboard
            </Link>
          ) : null}
        </div>
      </header>

      {oauthStatus === 'loading' ? <div className="dashboard-state">Completing OAuth…</div> : null}
      {pagesStatus === 'loading' ? <div className="dashboard-state">Loading pages…</div> : null}
      {error ? (
        <div className="dashboard-state" role="alert">
          {error}
        </div>
      ) : null}

      {missingRequiredPermissions.length > 0 ? (
        <div className="panel meta-warning-panel" role="status">
          <h3>Missing insights permissions</h3>
          <p>Re-run OAuth and grant required scopes: {missingRequiredPermissions.join(', ')}.</p>
        </div>
      ) : null}

      {pagesStatus === 'loaded' && pages.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No pages found"
          message="Connect Meta and select a page with ANALYZE permission."
          className="panel"
        />
      ) : null}

      {pages.length > 0 ? (
        <article className="panel">
          <h3>Available Pages</h3>
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Page</th>
                  <th className="dashboard-table__header-cell">Page ID</th>
                  <th className="dashboard-table__header-cell">Analyze eligible</th>
                  <th className="dashboard-table__header-cell">Default</th>
                  <th className="dashboard-table__header-cell">Action</th>
                </tr>
              </thead>
              <tbody>
                {pages.map((page) => (
                  <tr key={page.id} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{page.name}</td>
                    <td className="dashboard-table__cell">{page.page_id}</td>
                    <td className="dashboard-table__cell">{page.can_analyze ? 'Yes' : 'No'}</td>
                    <td className="dashboard-table__cell">{page.is_default ? 'Default' : '—'}</td>
                    <td className="dashboard-table__cell">
                      <button
                        className="button tertiary"
                        type="button"
                        disabled={!page.can_analyze}
                        onClick={() => {
                          void selectDefaultPage(page.page_id).then(() => {
                            navigate(`/dashboards/meta/pages/${page.page_id}/overview`);
                          }).catch(() => undefined);
                        }}
                      >
                        Select & Open
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

export default MetaIntegrationPage;
