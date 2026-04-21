import { useCallback, useEffect, useState } from 'react';

import RecommendationsTabSection from '../../components/google-ads/workspace/tab-sections/RecommendationsTabSection';
import { appendQueryParams } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import {
  fetchGoogleAdsList,
  type GoogleAdsListResponse,
} from '../../lib/googleAdsDashboard';
import type { GoogleAdsRecommendationRow } from '../../lib/googleAdsAggregates';
import useDashboardStore from '../../state/useDashboardStore';

/**
 * Legacy-mode Recommendations page (Sprint 3, S3c).
 *
 * Dropped the `GoogleAdsDataTablePage` wrapper so the legacy route renders
 * the viz-kit-styled `RecommendationsTabSection` directly (architect §6.9).
 * Dismiss button intentionally absent — no backend PATCH endpoint exists.
 */
const GoogleAdsRecommendationsPage = () => {
  const [payload, setPayload] = useState<GoogleAdsListResponse<GoogleAdsRecommendationRow>>({
    count: 0,
    results: [],
  });
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState('');

  const filters = useDashboardStore((state) => state.filters);

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading');
    setError('');
    try {
      const { start, end } = resolveFilterRange(filters);
      const path = appendQueryParams('/analytics/google-ads/recommendations/', {
        platforms: 'google_ads',
        customer_id: filters.accountId || undefined,
        start_date: start || undefined,
        end_date: end || undefined,
      });
      const response = await fetchGoogleAdsList<GoogleAdsRecommendationRow>(path);
      if (signal?.aborted) return;
      setPayload(response);
      setStatus('success');
    } catch (err) {
      if (signal?.aborted) return;
      setError(err instanceof Error ? err.message : 'Failed to load recommendations.');
      setStatus('error');
    }
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Recommendations & Opportunities</h1>
        <p className="dashboardSubtitle">
          Google Ads recommendation inventory for optimization opportunities.
        </p>
      </header>

      <RecommendationsTabSection data={payload} status={status} error={error} />
    </section>
  );
};

export default GoogleAdsRecommendationsPage;
