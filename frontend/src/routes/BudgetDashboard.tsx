import { useCallback, useMemo } from 'react';

import BudgetPacingList from '../components/BudgetPacingList';
import DashboardState from '../components/DashboardState';
import FilterStatus from '../components/FilterStatus';
import StatCard from '../components/ui/StatCard';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
import { formatCurrency, formatNumber } from '../lib/format';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';

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
  const { budget, campaign, budgetRows, availability } = useDashboardStore((state) => ({
    budget: state.budget,
    campaign: state.campaign,
    budgetRows: state.getBudgetRowsForSelectedParish(),
    availability: state.availability,
  }));
  const loadAll = useDashboardStore((state) => state.loadAll);
  const datasetMode = useDatasetStore((state) => state.mode);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const budgetAvailability = availability?.budget;
  const liveDatasetBlocked =
    datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;
  const shouldShowEmptyState =
    budgetAvailability?.status !== 'available' || (!budget.data && budget.status !== 'loading');
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const summaryCards = useMemo(() => {
    const over = budgetRows.filter((row) => row.pacingPercent > 1.05).length;
    const under = budgetRows.filter((row) => row.pacingPercent < 0.95).length;
    const onTrack = budgetRows.length - over - under;
    const totalBudget = budgetRows.reduce(
      (sum, row) => sum + (row.windowBudget ?? row.monthlyBudget),
      0,
    );
    const totalProjectedSpend = budgetRows.reduce((sum, row) => sum + row.projectedSpend, 0);

    return [
      { label: 'Campaigns', value: formatNumber(budgetRows.length) },
      { label: 'On track', value: formatNumber(onTrack) },
      { label: 'Under pace', value: formatNumber(under) },
      { label: 'Over pace', value: formatNumber(over) },
      { label: 'Budgeted', value: formatCurrency(totalBudget, currency) },
      { label: 'Projected', value: formatCurrency(totalProjectedSpend, currency) },
    ];
  }, [budgetRows, currency]);

  if (budget.status === 'loading' && !budget.data) {
    return <DashboardState variant="loading" layout="page" message="Loading budget pacing..." />;
  }

  if (budget.status === 'error' && !budget.data) {
    if (liveDatasetBlocked) {
      return (
        <div className="dashboard-grid single-panel">
          <section className="panel full-width">
            <DashboardState
              variant="empty"
              icon={<BudgetEmptyIcon />}
              title={titleForLiveDatasetReason(liveReason)}
              message={liveDatasetMessage ?? 'Live warehouse metrics are unavailable.'}
              actionLabel="Refresh data"
              onAction={handleRetry}
              layout="panel"
            />
          </section>
        </div>
      );
    }
    const errorTitle =
      budget.errorKind === 'stale_snapshot'
        ? 'Dashboard data is refreshing'
        : budget.errorKind === 'network'
          ? 'Unable to connect'
          : 'Budget pacing';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="error"
            title={errorTitle}
            message={budget.error ?? 'Unable to load budget pacing.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  if (shouldShowEmptyState) {
    const emptyVariant = budgetAvailability?.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      budgetAvailability?.reason === 'budget_unavailable'
        ? 'Budgets are unavailable for this view'
        : budgetAvailability?.reason === 'no_matching_filters'
          ? 'No budget rows match this view'
          : budgetAvailability?.reason === 'no_recent_data'
            ? 'No recent reportable data'
            : 'No budget pacing yet';
    const emptyMessage =
      budgetAvailability?.reason === 'budget_unavailable'
        ? 'Campaign performance exists, but no Meta ad set budgets were available for the selected client and range.'
        : budgetAvailability?.reason === 'no_matching_filters'
          ? 'No budget rows matched the selected client, range, or search filters.'
          : budgetAvailability?.reason === 'no_recent_data'
            ? 'The selected Meta account is connected, but Meta returned no recent reportable budget-backed delivery for this window.'
            : 'Budget pacing will appear once campaign budgets are configured.';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant={emptyVariant}
            icon={<BudgetEmptyIcon />}
            title={emptyTitle}
            message={emptyMessage}
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
    <div className="dashboardGrid">
      <div className="kpiColumn" role="group" aria-label="Budget KPIs">
        {summaryCards.map((card) => (
          <StatCard key={card.label} label={card.label} value={card.value} />
        ))}
      </div>

      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Budget pacing</h2>
            <FilterStatus />
          </div>
          <p className="muted">Compare projected spend against the selected-window Meta budget plan.</p>
        </header>
        <BudgetPacingList rows={budgetRows} currency={currency} />
      </section>
    </div>
  );
};

export default BudgetDashboard;
