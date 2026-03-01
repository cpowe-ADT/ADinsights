import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import useMetaStore from '../state/useMetaStore';

function resolveCampaignsErrorMessage(errorCode?: string, fallback?: string): string {
  if (errorCode === 'token_expired') {
    return 'Meta token expired. Reconnect Meta from Data Sources and retry.';
  }
  if (errorCode === 'permission_error') {
    return 'Missing Meta permissions. Re-run OAuth with required scopes.';
  }
  if (errorCode === 'rate_limited') {
    return 'Meta API is rate-limiting requests. Retry in a moment.';
  }
  return fallback ?? 'Try again.';
}

const MetaCampaignOverviewPage = () => {
  const { filters, setFilters, accounts, campaigns, loadAccounts, loadCampaigns } = useMetaStore(
    (state) => ({
      filters: state.filters,
      setFilters: state.setFilters,
      accounts: state.accounts,
      campaigns: state.campaigns,
      loadAccounts: state.loadAccounts,
      loadCampaigns: state.loadCampaigns,
    }),
  );

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    void loadCampaigns();
  }, [
    filters.accountId,
    filters.search,
    filters.status,
    filters.since,
    filters.until,
    loadCampaigns,
  ]);

  const activeCount = useMemo(
    () => campaigns.rows.filter((row) => row.status.toUpperCase().includes('ACTIVE')).length,
    [campaigns.rows],
  );

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Campaign overview</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/accounts">
            Account list
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/insights">
            Insights dashboard
          </Link>
        </div>
      </header>

      <div className="dashboard-grid" style={{ marginBottom: '1rem' }}>
        <article className="panel">
          <h3>Total campaigns</h3>
          <strong>{campaigns.count}</strong>
        </article>
        <article className="panel">
          <h3>Active campaigns</h3>
          <strong>{activeCount}</strong>
        </article>
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Account</span>
            <select
              value={filters.accountId}
              onChange={(event) =>
                setFilters({
                  accountId: event.target.value,
                  campaignId: '',
                  adsetId: '',
                })
              }
            >
              <option value="">All ad accounts</option>
              {accounts.rows.map((account) => (
                <option key={account.id} value={account.external_id}>
                  {account.name || account.external_id}
                </option>
              ))}
            </select>
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Status</span>
            <input
              value={filters.status}
              onChange={(event) => setFilters({ status: event.target.value })}
              placeholder="ACTIVE / PAUSED"
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Search</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Campaign name"
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Since</span>
            <input
              type="date"
              value={filters.since}
              onChange={(event) => setFilters({ since: event.target.value })}
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Until</span>
            <input
              type="date"
              value={filters.until}
              onChange={(event) => setFilters({ until: event.target.value })}
            />
          </label>
          <button type="button" className="button secondary" onClick={() => void loadCampaigns()}>
            Refresh
          </button>
        </div>
      </div>

      {campaigns.status === 'loading' && campaigns.rows.length === 0 ? (
        <div className="dashboard-state dashboard-state--page">Loading campaigns...</div>
      ) : null}

      {campaigns.status === 'stale' ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          Showing stale campaign data.{' '}
          {resolveCampaignsErrorMessage(campaigns.errorCode, campaigns.error)}
        </div>
      ) : null}

      {campaigns.status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load campaigns"
          message={resolveCampaignsErrorMessage(campaigns.errorCode, campaigns.error)}
          actionLabel="Retry"
          onAction={() => void loadCampaigns()}
          className="panel"
        />
      ) : null}

      {campaigns.status !== 'error' && campaigns.rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No campaigns found"
          message="Try different filters or run hierarchy sync."
          className="panel"
        />
      ) : null}

      {campaigns.rows.length > 0 ? (
        <div className="panel">
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Campaign</th>
                  <th className="dashboard-table__header-cell">External ID</th>
                  <th className="dashboard-table__header-cell">Status</th>
                  <th className="dashboard-table__header-cell">Objective</th>
                  <th className="dashboard-table__header-cell">Account</th>
                  <th className="dashboard-table__header-cell">Updated</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.rows.map((row) => (
                  <tr key={row.id} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{row.name}</td>
                    <td className="dashboard-table__cell">{row.external_id}</td>
                    <td className="dashboard-table__cell">{row.status || '—'}</td>
                    <td className="dashboard-table__cell">{row.objective || '—'}</td>
                    <td className="dashboard-table__cell">{row.account_external_id || '—'}</td>
                    <td className="dashboard-table__cell">{row.updated_time || row.updated_at}</td>
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

export default MetaCampaignOverviewPage;
