import { useEffect, useState } from 'react';

import { appendQueryParams, get } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';
import PmaxTabSection from '../../components/google-ads/workspace/tab-sections/PmaxTabSection';
import type { GoogleAdsAssetGroupRow } from '../../lib/googleAdsCreativeConvAggregates';

type PmaxPayload = {
  count?: number;
  results?: GoogleAdsAssetGroupRow[];
};

/**
 * Sprint 3 — Legacy PMax page.
 *
 * Rewritten per architect §8.2 — renders the new `AssetGroupTreemap`
 * viz-kit primitive in the workspace `PmaxTabSection`.
 */
const GoogleAdsPmaxPage = () => {
  const [data, setData] = useState<PmaxPayload | null>(null);
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
        const path = appendQueryParams(
          '/analytics/google-ads/pmax/asset-groups/',
          {
            platforms: 'google_ads',
            customer_id: filters.accountId || undefined,
            start_date: start || undefined,
            end_date: end || undefined,
          },
        );
        const response = await get<PmaxPayload>(path);
        if (!active) return;
        setData(response);
        setStatus('success');
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load PMax asset groups.',
        );
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
        <h1 className="dashboardHeading">Performance Max</h1>
        <p className="dashboardSubtitle">
          Asset group performance and top drivers for Performance Max campaigns.
        </p>
      </header>
      <PmaxTabSection data={data ?? {}} status={status} error={error} />
    </section>
  );
};

export default GoogleAdsPmaxPage;
