import { useCallback, useEffect, useState } from 'react';

import ChangesTabSection from '../../components/google-ads/workspace/tab-sections/ChangesTabSection';
import { appendQueryParams } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import {
  fetchGoogleAdsList,
  type GoogleAdsListResponse,
} from '../../lib/googleAdsDashboard';
import type { GoogleAdsChangeRow } from '../../lib/googleAdsAggregates';
import useDashboardStore from '../../state/useDashboardStore';

/**
 * Legacy-mode Change Log page (Sprint 3, S3c).
 *
 * Dropped the `GoogleAdsDataTablePage` wrapper so the legacy route renders
 * the viz-kit-styled `ChangesTabSection` directly (architect §6.8). The
 * paginated endpoint contract (`page / page_size / num_pages`) is preserved
 * by consuming the raw response from `fetchGoogleAdsList`.
 */
const GoogleAdsChangeLogPage = () => {
  const [payload, setPayload] = useState<GoogleAdsListResponse<GoogleAdsChangeRow>>({
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
      const path = appendQueryParams('/analytics/google-ads/change-events/', {
        platforms: 'google_ads',
        customer_id: filters.accountId || undefined,
        start_date: start || undefined,
        end_date: end || undefined,
      });
      const response = await fetchGoogleAdsList<GoogleAdsChangeRow>(path);
      if (signal?.aborted) return;
      setPayload(response);
      setStatus('success');
    } catch (err) {
      if (signal?.aborted) return;
      setError(err instanceof Error ? err.message : 'Failed to load change events.');
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
        <h1 className="dashboardHeading">Change Log & Governance</h1>
        <p className="dashboardSubtitle">
          Recent account-level changes (bids, budgets, ads, targeting) and metadata.
        </p>
      </header>

      <ChangesTabSection data={payload} status={status} error={error} />
    </section>
  );
};

export default GoogleAdsChangeLogPage;
