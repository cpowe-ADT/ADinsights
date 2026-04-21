import { useEffect, useMemo, useState } from 'react';

import PacingTabSection from '../../components/google-ads/workspace/tab-sections/PacingTabSection';
import { appendQueryParams, get } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import type { GoogleAdsPacingPayload } from '../../lib/googleAdsAggregates';
import useDashboardStore from '../../state/useDashboardStore';

const GoogleAdsBudgetPage = () => {
  const [data, setData] = useState<GoogleAdsPacingPayload | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState('');

  // NB2 fix (preserved): subscribe to filters so stale data is not shown.
  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const path = appendQueryParams('/analytics/google-ads/budgets/pacing/', {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
        const response = await get<GoogleAdsPacingPayload>(path);
        if (!active) return;
        setData(response);
        setStatus('success');
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load budget pacing.');
        setStatus('error');
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [filters]);

  const sectionStatus = useMemo(() => {
    if (status === 'loading') return 'loading' as const;
    if (status === 'error') return 'error' as const;
    if (status === 'success') return 'success' as const;
    return 'idle' as const;
  }, [status]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Budget & Pacing</h1>
        <p className="dashboardSubtitle">
          Spend pacing, forecast, and delivery risk guardrails.
        </p>
      </header>

      <PacingTabSection data={data} status={sectionStatus} error={error} />
    </section>
  );
};

export default GoogleAdsBudgetPage;
