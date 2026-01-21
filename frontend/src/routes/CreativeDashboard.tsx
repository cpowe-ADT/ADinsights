import { useCallback } from 'react';

import CreativeTable from '../components/CreativeTable';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import FullPageLoader from '../components/FullPageLoader';
import { useAuth } from '../auth/AuthContext';
import useDashboardStore from '../state/useDashboardStore';

const CreativeEmptyIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.2">
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M16 18h16M16 24h10" strokeLinecap="round" />
    <circle cx="32" cy="26" r="4" />
    <path d="m34.5 28.5 5 5" strokeLinecap="round" />
  </svg>
);

const CreativeDashboard = () => {
  const { tenantId } = useAuth();
  const { creative, campaign, creativeRows } = useDashboardStore((state) => ({
    creative: state.creative,
    campaign: state.campaign,
    creativeRows: state.getCreativeRowsForSelectedParish(),
  }));
  const loadAll = useDashboardStore((state) => state.loadAll);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  if (creative.status === 'loading' && !creative.data) {
    return <FullPageLoader message="Loading creative performance…" />;
  }

  if (creative.status === 'error' && !creative.data) {
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <ErrorState
            message={creative.error ?? 'Unable to load creative performance.'}
            retryLabel="Retry load"
            onRetry={handleRetry}
          />
        </section>
      </div>
    );
  }

  if (!creative.data) {
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <EmptyState
            icon={<CreativeEmptyIcon />}
            title="No creative insights yet"
            message="Creative performance will appear once ads begin accruing spend."
            actionLabel="Refresh data"
            actionVariant="secondary"
            onAction={handleRetry}
          />
        </section>
      </div>
    );
  }

  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <CreativeTable rows={creativeRows} currency={currency} />
      </section>
    </div>
  );
};

export default CreativeDashboard;
