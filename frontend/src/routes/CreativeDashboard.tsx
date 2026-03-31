import { useCallback, useMemo } from 'react';

import CreativeTable from '../components/CreativeTable';
import DashboardState from '../components/DashboardState';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { useAuth } from '../auth/AuthContext';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';
import useDashboardStore from '../state/useDashboardStore';

const CreativeEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M16 18h16M16 24h10" strokeLinecap="round" />
    <circle cx="32" cy="26" r="4" />
    <path d="m34.5 28.5 5 5" strokeLinecap="round" />
  </svg>
);

const CreativeDashboard = () => {
  const { tenantId } = useAuth();
  const { creative, campaign, creativeRows, availability } = useDashboardStore((state) => ({
    creative: state.creative,
    campaign: state.campaign,
    creativeRows: state.getCreativeRowsForSelectedParish(),
    availability: state.availability,
  }));
  const loadAll = useDashboardStore((state) => state.loadAll);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const creativeAvailability = availability?.creative;
  const shouldShowEmptyState =
    creativeAvailability?.status === 'empty' || (!creative.data && creative.status !== 'loading');
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  const summaryCards = useMemo(() => {
    const totalSpend = creativeRows.reduce((sum, row) => sum + row.spend, 0);
    const totalImpressions = creativeRows.reduce((sum, row) => sum + row.impressions, 0);
    const totalClicks = creativeRows.reduce((sum, row) => sum + row.clicks, 0);
    const totalConversions = creativeRows.reduce((sum, row) => sum + row.conversions, 0);
    const avgRoas = totalSpend > 0 ? totalConversions / totalSpend : 0;
    const avgCtr = totalImpressions > 0 ? totalClicks / totalImpressions : 0;

    return [
      { label: 'Creatives', value: formatNumber(creativeRows.length) },
      { label: 'Spend', value: formatCurrency(totalSpend, currency) },
      { label: 'CTR', value: formatRatio(avgCtr, 2) },
      { label: 'ROAS', value: formatRatio(avgRoas, 2) },
    ];
  }, [creativeRows, currency]);

  if (creative.status === 'loading' && !creative.data) {
    return (
      <DashboardState variant="loading" layout="page" message="Loading creative performance..." />
    );
  }

  if (creative.status === 'error' && !creative.data) {
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="error"
            message={creative.error ?? 'Unable to load creative performance.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  if (shouldShowEmptyState) {
    const emptyVariant = creativeAvailability?.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      creativeAvailability?.reason === 'no_matching_filters'
        ? 'No creatives match this view'
        : creativeAvailability?.reason === 'no_recent_data'
          ? 'No recent reportable data'
          : 'No creative insights yet';
    const emptyMessage =
      creativeAvailability?.reason === 'no_matching_filters'
        ? 'No creative rows matched the selected client, date range, or search filters.'
        : creativeAvailability?.reason === 'no_recent_data'
          ? 'The selected Meta account is connected, but Meta returned no recent reportable creative results for this window.'
          : 'Creative performance will appear once ads begin accruing spend.';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant={emptyVariant}
            icon={<CreativeEmptyIcon />}
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
      <div className="kpiColumn" role="group" aria-label="Creative KPIs">
        {summaryCards.map((card) => (
          <StatCard key={card.label} label={card.label} value={card.value} />
        ))}
      </div>

      <Card title="Creative leaderboard" className="tableCardWide">
        <CreativeTable rows={creativeRows} currency={currency} />
      </Card>
    </div>
  );
};

export default CreativeDashboard;
