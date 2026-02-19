import { useEffect } from 'react';
import { Link } from 'react-router-dom';

import EmptyState from '../components/EmptyState';
import useMetaStore from '../state/useMetaStore';

function resolveAccountsErrorMessage(errorCode?: string, fallback?: string): string {
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

const MetaAccountsPage = () => {
  const { accounts, filters, setFilters, loadAccounts } = useMetaStore((state) => ({
    accounts: state.accounts,
    filters: state.filters,
    setFilters: state.setFilters,
    loadAccounts: state.loadAccounts,
  }));

  useEffect(() => {
    void loadAccounts();
  }, [filters.search, filters.status, filters.since, filters.until, loadAccounts]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Ad accounts</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/campaigns">
            Campaign overview
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/insights">
            Insights dashboard
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/status">
            Connection status
          </Link>
        </div>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Search</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Name or account id"
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Status</span>
            <input
              value={filters.status}
              onChange={(event) => setFilters({ status: event.target.value })}
              placeholder="ACTIVE, DISABLED, ..."
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
          <button type="button" className="button secondary" onClick={() => void loadAccounts()}>
            Refresh
          </button>
        </div>
      </div>

      {accounts.status === 'loading' && accounts.rows.length === 0 ? (
        <div className="dashboard-state dashboard-state--page">Loading Meta accounts...</div>
      ) : null}

      {accounts.status === 'stale' ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          Showing stale account data. {resolveAccountsErrorMessage(accounts.errorCode, accounts.error)}
        </div>
      ) : null}

      {accounts.status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load Meta ad accounts"
          message={resolveAccountsErrorMessage(accounts.errorCode, accounts.error)}
          actionLabel="Retry"
          onAction={() => void loadAccounts()}
          className="panel"
        />
      ) : null}

      {accounts.status !== 'error' && accounts.rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No ad accounts yet"
          message="Connect Meta and run sync to populate ad accounts."
          className="panel"
        />
      ) : null}

      {accounts.rows.length > 0 ? (
        <div className="panel">
          <h2>Accounts ({accounts.count})</h2>
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  <th className="dashboard-table__header-cell">Name</th>
                  <th className="dashboard-table__header-cell">External ID</th>
                  <th className="dashboard-table__header-cell">Account ID</th>
                  <th className="dashboard-table__header-cell">Currency</th>
                  <th className="dashboard-table__header-cell">Status</th>
                  <th className="dashboard-table__header-cell">Business</th>
                </tr>
              </thead>
              <tbody>
                {accounts.rows.map((account) => (
                  <tr key={account.id} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{account.name || '—'}</td>
                    <td className="dashboard-table__cell">{account.external_id}</td>
                    <td className="dashboard-table__cell">{account.account_id || '—'}</td>
                    <td className="dashboard-table__cell">{account.currency || '—'}</td>
                    <td className="dashboard-table__cell">{account.status || '—'}</td>
                    <td className="dashboard-table__cell">{account.business_name || '—'}</td>
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

export default MetaAccountsPage;
