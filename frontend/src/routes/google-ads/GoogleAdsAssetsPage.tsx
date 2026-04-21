import { useEffect, useState } from 'react';

import { appendQueryParams, get } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';
import AssetsTabSection from '../../components/google-ads/workspace/tab-sections/AssetsTabSection';
import type { GoogleAdsAssetRow } from '../../lib/googleAdsCreativeConvAggregates';

type AssetsPayload = {
  count?: number;
  results?: GoogleAdsAssetRow[];
};

/**
 * Sprint 3 — Legacy Assets page.
 *
 * Rewritten per architect §8.2 to render the Sprint-1/Sprint-3 viz kit
 * directly instead of delegating to GoogleAdsDataTablePage. Pattern
 * mirrors GoogleAdsBudgetPage (NB2 filter subscription).
 */
const GoogleAdsAssetsPage = () => {
  const [data, setData] = useState<AssetsPayload | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>(
    'loading',
  );
  const [error, setError] = useState('');

  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const path = appendQueryParams('/analytics/google-ads/assets/', {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
        const response = await get<AssetsPayload>(path);
        if (!active) return;
        setData(response);
        setStatus('success');
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load assets.');
        setStatus('error');
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [filters]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Ads &amp; Assets</h1>
        <p className="dashboardSubtitle">
          Ad policy diagnostics and asset-level performance signals.
        </p>
      </header>
      <AssetsTabSection data={data ?? {}} status={status} error={error} />
    </section>
  );
};

export default GoogleAdsAssetsPage;
