import { useCallback } from 'react';

import BudgetPacingList from '../components/BudgetPacingList';
import DashboardState from '../components/DashboardState';
import FilterStatus from '../components/FilterStatus';
import { useAuth } from '../auth/AuthContext';
import useDashboardStore from '../state/useDashboardStore';

const BudgetEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M16 20h16M16 26h10" strokeLinecap="round" />
    <path d="M28 30h8" strokeLinecap="round" />
  </svg>
);

const BudgetDashboard = () => {
  const { tenantId } = useAuth();
  const { budget, campaign, budgetRows } = useDashboardStore((state) => ({
    budget: state.budget,
    campaign: state.campaign,
    budgetRows: state.getBudgetRowsForSelectedParish(),
  }));
  const loadAll = useDashboardStore((state) => state.loadAll);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  if (budget.status === 'loading' && !budget.data) {
    return <DashboardState variant="loading" layout="page" message="Loading budget pacing..." />;
  }

  if (budget.status === 'error' && !budget.data) {
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="error"
            message={budget.error ?? 'Unable to load budget pacing.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  if (!budget.data) {
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="empty"
            icon={<BudgetEmptyIcon />}
            title="No budget pacing yet"
            message="Budget pacing will appear once campaign budgets are configured."
            actionLabel="Refresh data"
            actionVariant="secondary"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Monthly pacing</h2>
            <FilterStatus />
          </div>
          <p className="muted">Compare current spend against planned budgets.</p>
        </header>
        <BudgetPacingList rows={budgetRows} currency={currency} />
      </section>
    </div>
  );
};

export default BudgetDashboard;
